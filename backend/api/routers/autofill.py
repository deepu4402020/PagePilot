"""
PagePilot — Autofill API Router (Structured Output Pipeline)

Design decision: This uses a SEPARATE pipeline from the chat agent because:
1. Form auto-fill needs deterministic, schema-guaranteed output (every field maps to a tool call)
2. The ReAct agent loop is non-deterministic — it may produce different tool call sequences
3. Structured output (with_structured_output) guarantees the response conforms to our Pydantic schema
4. This separation is the "dual-pipeline architecture" mentioned in the resume
"""

import json
import logging
from fastapi import APIRouter, HTTPException
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from backend.models.schemas import AutofillRequest, AutofillResponse
from backend.memory.profile_manager import get_user_facts

logger = logging.getLogger("pagepilot.autofill")

router = APIRouter()


# Structured output schema — guarantees deterministic JSON
class ToolCall(BaseModel):
    type: str = Field(description="The type of action: 'fill_input' or 'select_option'")
    selector: str = Field(description="The exact CSS selector of the element")
    value: str = Field(description="The value to fill or select")

class AutofillResult(BaseModel):
    tool_calls: list[ToolCall] = Field(
        description="List of tool calls to execute on the form"
    )


@router.post("/api/autofill", response_model=AutofillResponse)
async def autofill_endpoint(request: AutofillRequest):
    try:
        user_facts = get_user_facts()
        if not user_facts:
            return AutofillResponse(
                reply="No saved facts yet. Chat with me first and share your details (name, email, experience, etc.).",
                tool_calls=[]
            )

        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        structured_llm = llm.with_structured_output(AutofillResult)

        system_prompt = """You are PagePilot's auto-fill engine. Your job is to match saved user facts to form fields and generate precise fill actions.

Known Facts about the User:
{user_facts}

Form Elements on the page:
{page_context}

INSTRUCTIONS:
- Match each form field (by its label, text, type, placeholder) to the appropriate user fact.
- For text inputs and textareas, use type: "fill_input".
- For dropdowns/selects, use type: "select_option" with the closest matching option value.
- Use the EXACT selector from the form elements list.
- Only fill fields you can CONFIDENTLY match — do not guess.
- Skip fields with no clear match in the user's facts."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Auto-fill this form with my saved facts.")
        ])

        page_context_str = json.dumps(
            [el.model_dump() for el in request.page_context],
            indent=2
        )
        user_facts_str = "\n".join(f"- {fact}" for fact in user_facts)

        chain = prompt | structured_llm

        result: AutofillResult = await chain.ainvoke({
            "user_facts": user_facts_str,
            "page_context": page_context_str,
        })

        tool_calls = [tc.model_dump() for tc in result.tool_calls]
        matched_count = len(tool_calls)

        logger.info(f"Autofill: matched {matched_count} field(s) from {len(user_facts)} fact(s)")

        return AutofillResponse(
            reply=f"Matched {matched_count} field{'s' if matched_count != 1 else ''} to your profile.",
            tool_calls=tool_calls,
        )

    except Exception as e:
        logger.error(f"Autofill endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
