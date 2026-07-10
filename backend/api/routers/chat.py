from fastapi import APIRouter, HTTPException
import json
from langchain_core.messages import HumanMessage, AIMessage
from backend.models.schemas import ChatRequest, ChatResponse
from backend.agents.browser_agent import get_agent_executor
from backend.embeddings.vector_store import update_page_context, get_relevant_context
from backend.memory.profile_manager import get_user_facts

router = APIRouter()

@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # 1. Update RAG Context if page text is provided and tab_id exists
        if request.tab_id and request.page_text:
            update_page_context(request.tab_id, request.page_text)

        # 2. Retrieve relevant context based on user message
        rag_context = ""
        if request.tab_id:
            rag_context = get_relevant_context(request.message, request.tab_id)

        # 3. Format Page Elements for Agent Prompt
        page_context_str = json.dumps([el.model_dump() for el in request.page_context], indent=2)

        # 4. Format Chat History for LangChain
        chat_history = []
        for msg in request.history:
            if msg.role == 'user':
                chat_history.append(HumanMessage(content=msg.content))
            elif msg.role in ['assistant', 'system']:
                chat_history.append(AIMessage(content=msg.content))

        messages = chat_history + [HumanMessage(content=request.message)]

        # 5. Build system prompt and execute Agent
        user_facts_str = "\n".join(get_user_facts()) or "No facts saved yet."
        rag_context_str = rag_context if rag_context else "No semantic context available."
        
        system_prompt = f"""You are CareerOps Copilot, a powerful browser automation agent.
You have access to tools that can click, fill inputs, scroll, and navigate.
Your goal is to help the user interact with the current webpage based on their request.

If the user asks a question about the page content, use the provided RAG Context to answer them.
If the user asks you to perform an action, use your tools.
If the user shares personal details (e.g. name, experience, location), you MUST use the `save_user_fact` tool to memorize it.

CRITICAL: Do NOT return raw JSON blocks like ```json {{{{"tool": ...}}}} ```. You MUST use the native tool calling capability provided to you. Just call the function directly.

Saved Facts about the User (Use this to answer questions or fill forms):
{user_facts_str}

RAG Context (Extracted from the page):
{rag_context_str}

Available UI Elements on screen (use these exact selectors for tools):
{page_context_str}
"""

        agent_executor = get_agent_executor(system_prompt)
        
        result = await agent_executor.ainvoke({
            "messages": messages
        })

        if "messages" in result and len(result["messages"]) > 0:
            reply_text = result["messages"][-1].content
            if not reply_text:
                reply_text = "I completed the action."
        else:
            reply_text = "I completed the action."
        
        # 6. Extract tool calls from new AI messages
        tool_calls = []
        new_messages = result.get("messages", [])[len(messages):]
        for msg in new_messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc["name"] == "save_user_fact":
                        continue
                    tool_calls.append({
                        "type": tc["name"],
                        **tc["args"]
                    })

        return ChatResponse(reply=reply_text, tool_calls=tool_calls if tool_calls else None)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("Chat Endpoint Error:", e)
        raise HTTPException(status_code=500, detail=str(e))
