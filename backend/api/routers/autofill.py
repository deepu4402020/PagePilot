from fastapi import APIRouter, HTTPException
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from backend.models.schemas import AutofillRequest, AutofillResponse
from backend.memory.profile_manager import get_user_facts
from pydantic import BaseModel, Field
from typing import List

router = APIRouter()

# Structured output for tool calls
class ToolCall(BaseModel):
    type: str = Field(description="The type of action to perform, e.g., 'fill_input' or 'select_option'")
    selector: str = Field(description="The exact CSS selector of the element")
    value: str = Field(description="The value to fill or select")

class AutofillResult(BaseModel):
    tool_calls: List[ToolCall] = Field(description="List of tool calls to execute on the form")

@router.post("/api/autofill", response_model=AutofillResponse)
async def autofill_endpoint(request: AutofillRequest):
    try:
        # We will use Structured Output to guarantee JSON array of tool calls
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        structured_llm = llm.with_structured_output(AutofillResult)
        
        system_prompt = """You are CareerOps Copilot. Your job is to auto-fill a job application form using the user's saved facts.

Known Facts about the User:
{user_facts}

Form Elements on the page:
{page_context}

INSTRUCTIONS:
- Match each form field (by its label, text, type) to the appropriate profile value.
- For text inputs, use type: "fill_input".
- For dropdowns/selects, use type: "select_option".
- Use the EXACT selector from the form elements list.
- Only fill fields you can confidently match."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Auto-fill this form with my saved facts.")
        ])
        
        page_context_str = json.dumps([el.model_dump() for el in request.page_context], indent=2)
        user_facts_str = "\n".join(get_user_facts()) or "No facts saved yet."

        chain = prompt | structured_llm
        
        # Async invoke
        result: AutofillResult = await chain.ainvoke({
            "user_facts": user_facts_str,
            "page_context": page_context_str
        })
        
        tool_calls = [tc.model_dump() for tc in result.tool_calls]
        matched_count = len(tool_calls)
        
        return AutofillResponse(
            reply=f"Matched {matched_count} field{'s' if matched_count != 1 else ''} to your profile.",
            tool_calls=tool_calls
        )

    except Exception as e:
        print("Autofill Endpoint Error:", e)
        raise HTTPException(status_code=500, detail=str(e))
