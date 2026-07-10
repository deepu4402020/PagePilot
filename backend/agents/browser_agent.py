from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from backend.tools.browser_tools import get_all_tools
from backend.tools.memory_tools import save_user_fact
import os

def get_agent_executor(system_prompt: str):
    # Use gpt-4o as default, or fallback
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    tools = get_all_tools() + [save_user_fact]
    
    agent = create_react_agent(llm, tools, state_modifier=system_prompt)
    return agent
