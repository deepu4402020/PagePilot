"""
PagePilot — Pydantic Schemas for API Request/Response Models
"""

from pydantic import BaseModel, Field


class PageElement(BaseModel):
    """Represents an interactive element extracted from the webpage DOM."""
    selector: str = Field(description="Primary CSS selector")
    fallback_selectors: list[str] | None = Field(
        default=None,
        description="Prioritized fallback selector chain for resilient element targeting",
    )
    tagName: str
    type: str | None = None
    text: str = ""
    label: str = ""
    options: list[dict[str, str]] | None = None


class ChatMessage(BaseModel):
    """A single message in the chat history."""
    role: str
    content: str


class ChatRequest(BaseModel):
    """Request body for the /api/chat endpoint."""
    message: str
    page_context: list[PageElement]
    page_text: str = ""
    history: list[ChatMessage] = []
    tab_id: int | None = None


class ChatResponse(BaseModel):
    """Response body from the /api/chat endpoint."""
    reply: str
    tool_calls: list[dict] | None = None


class AutofillRequest(BaseModel):
    """Request body for the /api/autofill endpoint."""
    page_context: list[PageElement]


class AutofillResponse(BaseModel):
    """Response body from the /api/autofill endpoint."""
    reply: str
    tool_calls: list[dict] = []
