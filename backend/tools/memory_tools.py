from langchain_core.tools import tool
from typing import Dict, Any
from backend.memory.profile_manager import save_user_fact as _save_user_fact

@tool
def save_user_fact(fact: str) -> Dict[str, Any]:
    """Save an important fact about the user to persistent memory. Use this when the user shares their name, experience, location, email, or any other personal detail."""
    success = _save_user_fact(fact)
    if success:
        return {"success": True, "message": f"Successfully saved fact: {fact}"}
    return {"success": False, "message": "Failed to save fact."}
