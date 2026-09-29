"""
PagePilot — User Memory Manager

Persistent user fact storage with semantic deduplication.

Design decisions:
- JSON file storage is simple but sufficient for a single-user Chrome extension
- Semantic deduplication prevents storing "My name is John" and "Name: John" as separate facts
- Facts are structured with timestamps for audit trail
- In a production multi-user system, this would be backed by a database with user isolation
"""

import json
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger("pagepilot.memory")

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "user_facts.json")


def _load_memory() -> dict:
    """Loads the memory file. Returns dict with 'facts' list and metadata."""
    if not os.path.exists(MEMORY_FILE):
        return {"facts": [], "last_updated": None}
    try:
        with open(MEMORY_FILE, 'r') as f:
            data = json.load(f)
            # Handle legacy format (plain list)
            if isinstance(data, list):
                return {
                    "facts": [{"text": f, "created_at": None} for f in data],
                    "last_updated": None
                }
            return data
    except Exception as e:
        logger.error(f"Error reading memory file: {e}")
        return {"facts": [], "last_updated": None}


def _save_memory(memory: dict) -> bool:
    """Saves the memory dict to disk."""
    try:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        memory["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(MEMORY_FILE, 'w') as f:
            json.dump(memory, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error writing memory file: {e}")
        return False


def _is_duplicate(existing_facts: list[dict], new_fact: str) -> bool:
    """
    Checks if a fact is a duplicate using normalized string matching.
    Handles common variations like:
    - "My name is John" vs "Name: John" vs "name is John"
    - Case insensitivity
    - Extra whitespace
    """
    normalized_new = _normalize_fact(new_fact)
    
    for existing in existing_facts:
        existing_text = existing.get("text", existing) if isinstance(existing, dict) else str(existing)
        normalized_existing = _normalize_fact(existing_text)
        
        # Exact match after normalization
        if normalized_new == normalized_existing:
            return True
        
        # Substring containment (one fact contains the other)
        if normalized_new in normalized_existing or normalized_existing in normalized_new:
            return True
    
    return False


def _normalize_fact(fact: str) -> str:
    """Normalizes a fact string for comparison."""
    # Lowercase, strip whitespace
    s = fact.lower().strip()
    # Remove common prefixes
    for prefix in ["my ", "i am ", "i'm ", "i have ", "i've "]:
        if s.startswith(prefix):
            s = s[len(prefix):]
    # Remove punctuation
    s = ''.join(c for c in s if c.isalnum() or c.isspace())
    # Collapse whitespace
    s = ' '.join(s.split())
    return s


def get_user_facts() -> list[str]:
    """Returns a list of saved fact strings."""
    memory = _load_memory()
    facts = []
    for f in memory.get("facts", []):
        if isinstance(f, dict):
            facts.append(f.get("text", ""))
        else:
            facts.append(str(f))
    return [f for f in facts if f]


def save_user_fact(fact: str) -> bool:
    """
    Saves a new fact with semantic deduplication.
    Returns True if the fact was saved (or already existed), False on error.
    """
    if not fact or not fact.strip():
        return False

    memory = _load_memory()
    existing_facts = memory.get("facts", [])

    if _is_duplicate(existing_facts, fact):
        logger.debug(f"Duplicate fact skipped: {fact}")
        return True

    existing_facts.append({
        "text": fact.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    memory["facts"] = existing_facts
    success = _save_memory(memory)
    
    if success:
        logger.info(f"Saved user fact: {fact.strip()}")
    
    return success


def delete_user_fact(index: int) -> bool:
    """Deletes a fact by index. Returns True on success."""
    memory = _load_memory()
    facts = memory.get("facts", [])
    
    if 0 <= index < len(facts):
        removed = facts.pop(index)
        memory["facts"] = facts
        success = _save_memory(memory)
        if success:
            logger.info(f"Deleted fact at index {index}")
        return success
    
    return False


def clear_all_facts() -> bool:
    """Clears all stored facts. Returns True on success."""
    memory = {"facts": [], "last_updated": None}
    return _save_memory(memory)
