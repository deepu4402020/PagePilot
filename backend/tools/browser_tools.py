from langchain_core.tools import tool
from typing import Dict, Any

@tool
def click_element(selector: str) -> Dict[str, Any]:
    """Click an element on the webpage using its CSS selector."""
    return {"type": "click", "selector": selector}

@tool
def fill_input(selector: str, value: str) -> Dict[str, Any]:
    """Fill an input field on the webpage using its CSS selector with a specific value."""
    return {"type": "fill_input", "selector": selector, "value": value}

@tool
def select_option(selector: str, value: str) -> Dict[str, Any]:
    """Select an option in a dropdown menu on the webpage using its CSS selector and the option value."""
    return {"type": "select_option", "selector": selector, "value": value}

@tool
def scroll_page(amount: int = 500) -> Dict[str, Any]:
    """Scroll the webpage vertically by the specified amount of pixels."""
    return {"type": "scroll_page", "amount": amount}

@tool
def navigate(url: str) -> Dict[str, Any]:
    """Navigate to a new URL."""
    return {"type": "navigate", "url": url}

def get_all_tools():
    return [click_element, fill_input, select_option, scroll_page, navigate]
