"""
PagePilot — Custom LangGraph StateGraph

Architecture:
  ┌─────────────────────────────────────────────────────────────┐
  │  START                                                       │
  │    │                                                         │
  │    ▼                                                         │
  │  ┌──────────────────┐                                       │
  │  │ classify_intent  │  (LLM classifies user intent)         │
  │  └──────┬───────────┘                                       │
  │         │                                                    │
  │    ┌────┼────────┬──────────┐                               │
  │    ▼    ▼        ▼          ▼                               │
  │  browse rag    memory    general                            │
  │    │    │        │          │                               │
  │    ▼    ▼        ▼          │                               │
  │  ┌────────┐  ┌────────┐    │                               │
  │  │execute │  │retrieve│    │                               │
  │  │_tools  │  │_context│    │                               │
  │  └───┬────┘  └───┬────┘    │                               │
  │      │           │         │                               │
  │      └─────┬─────┘         │                               │
  │            ▼               │                               │
  │      ┌──────────────┐      │                               │
  │      │  generate    │◄─────┘                               │
  │      │  _response   │                                       │
  │      └──────┬───────┘                                       │
  │             │                                               │
  │             ▼                                               │
  │           END                                               │
  └─────────────────────────────────────────────────────────────┘

Why this topology (interview talking points):
1. Intent classification BEFORE tool selection reduces wasted LLM calls
   - RAG queries skip the tool-calling agent entirely
   - General chat skips both RAG retrieval and tool calling
2. Conditional routing enables specialized prompts per intent type
3. Explicit state management makes the pipeline debuggable and testable
4. Memory extraction happens as a side-effect in classify_intent, not as a tool call,
   reducing latency for the common case
"""

import json
import logging
from typing import TypedDict, Literal, Optional, Annotated
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from backend.tools.browser_tools import get_all_tools
from backend.memory.profile_manager import get_user_facts, save_user_fact

logger = logging.getLogger("pagepilot.agent")

# Module-level LLM singletons — one client, reused across all node calls
# ponytail: single model name; swap to env-var if multi-model support is needed
_LLM_PRECISE = ChatOpenAI(model="gpt-4o", temperature=0)
_LLM_CHAT = ChatOpenAI(model="gpt-4o", temperature=0.3)

# ============================================================
# State Schema
# ============================================================

class AgentState(TypedDict):
    """Typed state that flows through the LangGraph pipeline."""
    # Input
    messages: list                              # Chat history (LangChain message objects)
    user_message: str                           # Current user message
    page_context_str: str                       # Serialized page elements
    rag_context: str                            # Retrieved RAG chunks
    user_facts: str                             # Serialized user facts

    # Pipeline state
    intent: str                                 # Classified intent
    extracted_facts: list                        # Facts to save from this message
    tool_calls: list                            # Browser tool calls to execute
    response: str                               # Final response text
    error: Optional[str]                        # Error message if any


# ============================================================
# Intent Classification (Structured Output)
# ============================================================

class IntentClassification(BaseModel):
    """Structured output for intent classification."""
    intent: Literal["browser_action", "page_question", "memory_save", "general_chat"] = Field(
        description="The classified intent of the user's message"
    )
    reasoning: str = Field(
        description="Brief explanation of why this intent was chosen"
    )
    extracted_facts: list[str] = Field(
        default_factory=list,
        description="Any personal facts the user shared (name, email, experience, etc.) that should be saved to memory"
    )


def classify_intent(state: AgentState) -> dict:
    """
    Node 1: Classify user intent and extract any personal facts.
    Uses structured output for deterministic classification.
    """
    try:
        structured_llm = _LLM_PRECISE.with_structured_output(IntentClassification)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intent classifier for PagePilot, a browser automation assistant.
Classify the user's message into exactly one of these intents:

- "browser_action": User wants to interact with the page (click, fill, scroll, navigate, select)
- "page_question": User is asking a question about the page content
- "memory_save": User is explicitly asking to save/remember something (rare, usually facts are extracted automatically)
- "general_chat": General conversation, greetings, help requests, or questions not about page content

Also extract any personal facts the user shares (name, email, phone, location, experience, education, skills, etc.)

Page elements visible: {page_context}
User's saved facts: {user_facts}"""),
            ("user", "{user_message}")
        ])

        chain = prompt | structured_llm
        result: IntentClassification = chain.invoke({
            "user_message": state["user_message"],
            "page_context": state["page_context_str"][:2000],  # Truncate for classification
            "user_facts": state["user_facts"]
        })

        # Side-effect: save any extracted facts immediately
        for fact in result.extracted_facts:
            save_user_fact(fact)
            logger.info(f"Saved user fact: {fact}")

        logger.info(f"Intent classified: {result.intent} | Reasoning: {result.reasoning}")

        return {
            "intent": result.intent,
            "extracted_facts": result.extracted_facts,
        }

    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        # Fallback: treat as general chat
        return {
            "intent": "general_chat",
            "extracted_facts": [],
            "error": f"Intent classification failed: {str(e)}"
        }


# ============================================================
# Intent Router
# ============================================================

def route_by_intent(state: AgentState) -> str:
    """Conditional edge: routes to the appropriate node based on classified intent."""
    intent = state.get("intent", "general_chat")
    if intent == "browser_action":
        return "execute_tools"
    if intent == "page_question":
        return "retrieve_context"
    return "generate_response"


# ============================================================
# RAG Retrieval Node
# ============================================================

def retrieve_context(state: AgentState) -> dict:
    """
    Node 2a: Retrieve relevant context from ChromaDB for page questions.
    Only called when intent is 'page_question'.
    """
    # RAG context is already injected by the router (chat.py)
    # This node passes it through but could do re-ranking or filtering
    rag_context = state.get("rag_context", "")

    if not rag_context or rag_context == "No semantic context available.":
        logger.warning("No RAG context available for page question")
        return {"rag_context": "No relevant context found on this page."}

    logger.info(f"RAG context retrieved: {len(rag_context)} chars")
    return {"rag_context": rag_context}


# ============================================================
# Tool Execution Node (ReAct-style for browser actions)
# ============================================================

def execute_tools(state: AgentState) -> dict:
    """
    Node 2b: Execute browser actions using LLM tool calling.
    Uses a focused prompt that only includes browser tools.
    """
    try:
        tools = get_all_tools()
        tool_map: dict[str, object] = {t.name: t for t in tools}
        llm_with_tools = _LLM_PRECISE.bind_tools(tools)

        system_prompt = f"""You are PagePilot's browser automation engine.
Your ONLY job is to select and call the correct browser tool(s) to fulfill the user's request.

Available UI elements on screen (use these EXACT selectors):
{state['page_context_str']}

User's known facts (for filling forms):
{state['user_facts']}

RULES:
- Call tools using the provided functions. Do NOT output JSON manually.
- Use the EXACT selectors from the page elements list.
- For filling inputs, use the user's known facts when relevant.
- You may call multiple tools in sequence if needed.
- After calling tools, briefly confirm what you did."""

        messages = [SystemMessage(content=system_prompt)] + state["messages"]

        # Run the tool-calling loop (up to 3 iterations)
        tool_calls_collected = []
        for iteration in range(3):
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                break

            # Process each tool call
            for tc in response.tool_calls:
                tool_fn = tool_map.get(tc["name"])
                if tool_fn:
                    result = tool_fn.invoke(tc["args"])
                    tool_calls_collected.append({"type": tc["name"], **tc["args"]})
                    messages.append(ToolMessage(
                        content=json.dumps(result),
                        tool_call_id=tc["id"],
                    ))

        # Extract final text response
        final_response = messages[-1].content if messages[-1].content else "Actions completed."

        logger.info(f"Executed {len(tool_calls_collected)} tool call(s)")
        return {
            "tool_calls": tool_calls_collected,
            "response": final_response,
        }

    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {
            "tool_calls": [],
            "response": f"I encountered an error while trying to interact with the page: {str(e)}",
            "error": str(e),
        }


# ============================================================
# Response Generation Node
# ============================================================

def generate_response(state: AgentState) -> dict:
    """
    Node 3: Generate the final response to the user.
    Uses different prompts based on the intent that was classified.
    """
    try:
        intent = state.get("intent", "general_chat")

        # If tool execution already generated a response, pass it through
        if intent == "browser_action" and state.get("response"):
            return {"response": state["response"]}

        # Build intent-specific prompt
        if intent == "page_question":
            system_prompt = f"""You are PagePilot, an AI browser assistant. Answer the user's question about the current webpage.
Use ONLY the provided context to answer. If the context doesn't contain the answer, say so honestly.

Page Context (from RAG retrieval):
{state.get('rag_context', 'No context available.')}

User's saved facts:
{state['user_facts']}

Be concise and cite specific parts of the page when possible."""

        elif intent == "memory_save":
            facts_saved = state.get("extracted_facts", [])
            if facts_saved:
                return {"response": f"Got it! I've saved: {', '.join(facts_saved)}. I'll use these to help fill forms and personalize my assistance."}
            else:
                return {"response": "I didn't catch any specific facts to save. Could you tell me more details like your name, email, experience, or skills?"}

        else:  # general_chat
            system_prompt = f"""You are PagePilot, a friendly AI browser assistant. You help users navigate and interact with web pages.

You can:
- Answer questions about the current page content
- Click buttons, fill forms, scroll, and navigate
- Remember personal details for auto-filling applications
- Auto-fill job application forms

User's saved facts:
{state['user_facts']}

Be concise and helpful. If the user seems to want a page action, suggest they describe what they'd like you to do."""

        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = _LLM_CHAT.invoke(messages)

        return {"response": response.content}

    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        return {
            "response": "I'm sorry, I encountered an error generating a response. Please try again.",
            "error": str(e),
        }


# ============================================================
# Graph Construction
# ============================================================

def build_agent_graph() -> StateGraph:
    """
    Builds and compiles the PagePilot agent graph.

    Graph topology:
        classify_intent ──┬── browser_action ──► execute_tools ──► generate_response ──► END
                          ├── page_question ──► retrieve_context ──► generate_response ──► END
                          ├── memory_save ──► generate_response ──► END
                          └── general_chat ──► generate_response ──► END
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("generate_response", generate_response)

    # Set entry point
    graph.set_entry_point("classify_intent")

    # Add conditional routing from intent classifier
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "execute_tools": "execute_tools",
            "retrieve_context": "retrieve_context",
            "generate_response": "generate_response",
        }
    )

    # Linear edges after routing
    graph.add_edge("retrieve_context", "generate_response")
    graph.add_edge("execute_tools", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()


# Module-level compiled graph (singleton)
agent_graph = build_agent_graph()
