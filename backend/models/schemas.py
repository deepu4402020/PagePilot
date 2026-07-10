from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class PageElement(BaseModel):
    selector: str
    tagName: str
    type: Optional[str] = None
    text: str = ""
    label: str = ""
    options: Optional[List[Dict[str, str]]] = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    profile: str
    page_context: List[PageElement]
    page_text: str = ""
    history: List[ChatMessage] = []
    tab_id: Optional[int] = None

class ChatResponse(BaseModel):
    reply: str
    tool_calls: Optional[List[Dict[str, Any]]] = None

class AutofillRequest(BaseModel):
    profile: Dict[str, Any]
    page_context: List[PageElement]

class AutofillResponse(BaseModel):
    reply: str
    tool_calls: List[Dict[str, Any]] = []
