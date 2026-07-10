from fastapi import APIRouter, HTTPException
import json
from langchain_core.messages import HumanMessage, AIMessage
from backend.models.schemas import ChatRequest, ChatResponse
from backend.agents.browser_agent import get_agent_executor
from backend.embeddings.vector_store import update_page_context, get_relevant_context
from backend.memory.profile_manager import get_user_facts

router = APIRouter()

@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # 1. Update RAG Context if page text is provided and tab_id exists
        if request.tab_id and request.page_text:
            update_page_context(request.tab_id, request.page_text)

        # 2. Retrieve relevant context based on user message
        rag_context = ""
        if request.tab_id:
            rag_context = get_relevant_context(request.message, request.tab_id)

        # 3. Format Page Elements for Agent Prompt
        page_context_str = json.dumps([el.model_dump() for el in request.page_context], indent=2)

        # 4. Format Chat History for LangChain
        chat_history = []
        for msg in request.history:
            if msg.role == 'user':
                chat_history.append(HumanMessage(content=msg.content))
            elif msg.role in ['assistant', 'system']:
                chat_history.append(AIMessage(content=msg.content))

        # 5. Execute Agent (Async)
        agent_executor = get_agent_executor()
        
        result = await agent_executor.ainvoke({
            "input": request.message,
            "user_facts": "\n".join(get_user_facts()) or "No facts saved yet.",
            "rag_context": rag_context if rag_context else "No semantic context available.",
            "page_elements": page_context_str,
            "chat_history": chat_history
        })

        reply_text = result.get("output", "I completed the action.")
        
        # 6. Extract tool calls from intermediate steps (if any)
        tool_calls = []
        intermediate_steps = result.get("intermediate_steps", [])
        for action, observation in intermediate_steps:
            # Langchain action gives us the tool name and tool input
            tool_calls.append({
                "type": action.tool,
                **action.tool_input
            })

        return ChatResponse(reply=reply_text, tool_calls=tool_calls if tool_calls else None)

    except Exception as e:
        print("Chat Endpoint Error:", e)
        raise HTTPException(status_code=500, detail=str(e))
