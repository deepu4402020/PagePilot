"""
PagePilot — Memory Tools for LangGraph Agent

Note: In the custom StateGraph, memory extraction happens as a side-effect
of intent classification (not as a tool call). These tools are kept as
standalone utilities that can be used by other parts of the system.
"""

from langchain_core.tools import tool
from backend.memory.profile_manager import save_user_fact as _save_user_fact


@tool
def save_user_fact(fact: str) -> dict:
    """Save an important fact about the user to persistent memory.
    Use this when the user shares their name, experience, location, email,
    phone number, education, skills, or any other personal detail."""
    success = _save_user_fact(fact)
    if success:
        return {"success": True, "message": f"Saved: {fact}"}
    return {"success": False, "message": "Failed to save fact."}
