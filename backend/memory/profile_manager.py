import json
import os
from typing import List

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "user_facts.json")

def get_user_facts() -> List[str]:
    """Returns a list of saved facts about the user."""
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading memory file: {e}")
        return []

def save_user_fact(fact: str) -> bool:
    """Appends a new fact about the user to the persistent memory."""
    facts = get_user_facts()
    if fact not in facts:
        facts.append(fact)
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
            with open(MEMORY_FILE, 'w') as f:
                json.dump(facts, f, indent=2)
            return True
        except Exception as e:
            print(f"Error writing to memory file: {e}")
            return False
    return True
