from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from backend.tools.browser_tools import get_all_tools
import os

def get_agent_executor():
    # Use gpt-4o as default, or fallback
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    tools = get_all_tools()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are CareerOps Copilot, a powerful browser automation agent.
You have access to tools that can click, fill inputs, scroll, and navigate.
Your goal is to help the user interact with the current webpage based on their request.

If the user asks a question about the page content, use the provided RAG Context to answer them.
If the user asks you to perform an action, use your tools. 

CRITICAL: Do NOT return raw JSON blocks like ```json {{"tool": ...}} ```. You MUST use the native tool calling capability provided to you. Just call the function directly.

Current Profile: {profile}

RAG Context (Extracted from the page):
{rag_context}

Available UI Elements on screen (use these exact selectors for tools):
{page_elements}
"""),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, return_intermediate_steps=True)
    return agent_executor
