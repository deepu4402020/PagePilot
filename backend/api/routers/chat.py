"""
PagePilot — Chat API Router

Integrates the custom LangGraph StateGraph agent with the FastAPI endpoint.
Handles message formatting, RAG context injection, and tool call extraction.
"""

import json
import logging
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage
from backend.models.schemas import ChatRequest, ChatResponse
from backend.agents.browser_agent import agent_graph
from backend.embeddings.vector_store import update_page_context, get_relevant_context
from backend.memory.profile_manager import get_user_facts

logger = logging.getLogger("pagepilot.chat")

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # 1. Update RAG context if page text is provided
        if request.tab_id and request.page_text:
            indexed = update_page_context(
                tab_id=request.tab_id,
                page_text=request.page_text,
            )
            if indexed:
                logger.info(f"Tab {request.tab_id}: new page content indexed")

        # 2. Retrieve relevant RAG context
        rag_context = ""
        if request.tab_id:
            rag_context = get_relevant_context(request.message, request.tab_id)

        # 3. Format page elements
        page_context_str = json.dumps(
            [el.model_dump() for el in request.page_context],
            indent=2
        )

        # 4. Format chat history as LangChain messages
        chat_history = []
        for msg in request.history:
            if msg.role == 'user':
                chat_history.append(HumanMessage(content=msg.content))
            elif msg.role in ('assistant', 'system'):
                chat_history.append(AIMessage(content=msg.content))

        messages = chat_history + [HumanMessage(content=request.message)]

        # 5. Prepare user facts
        user_facts_str = "\n".join(get_user_facts()) or "No facts saved yet."

        # 6. Invoke the LangGraph agent
        initial_state = {
            "messages": messages,
            "user_message": request.message,
            "page_context_str": page_context_str,
            "rag_context": rag_context if rag_context else "No semantic context available.",
            "user_facts": user_facts_str,
            "intent": "",
            "extracted_facts": [],
            "tool_calls": [],
            "response": "",
            "error": None,
        }

        result = await agent_graph.ainvoke(initial_state)

        # 7. Extract response and tool calls
        response_text = result.get("response", "I completed the action.")
        tool_calls = result.get("tool_calls", [])

        logger.info(
            f"Chat completed | intent={result.get('intent')} | "
            f"tools={len(tool_calls)} | facts_saved={len(result.get('extracted_facts', []))}"
        )

        return ChatResponse(
            reply=response_text,
            tool_calls=tool_calls if tool_calls else None,
        )

    except Exception as e:
        logger.exception(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
