from langchain_core.tools import tool


@tool
def click_element(selector: str) -> dict:
    """Click an element on the webpage using its CSS selector."""
    return {"type": "click", "selector": selector}


@tool
def fill_input(selector: str, value: str) -> dict:
    """Fill an input field on the webpage using its CSS selector with a specific value."""
    return {"type": "fill_input", "selector": selector, "value": value}


@tool
def select_option(selector: str, value: str) -> dict:
    """Select an option in a dropdown menu on the webpage using its CSS selector and the option value."""
    return {"type": "select_option", "selector": selector, "value": value}


@tool
def scroll_page(amount: int = 500) -> dict:
    """Scroll the webpage vertically by the specified amount of pixels."""
    return {"type": "scroll_page", "amount": amount}


@tool
def navigate(url: str) -> dict:
    """Navigate to a new URL."""
    return {"type": "navigate", "url": url}


def get_all_tools() -> list:
    return [click_element, fill_input, select_option, scroll_page, navigate]
