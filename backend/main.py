from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables (like OPENAI_API_KEY)
load_dotenv()

app = FastAPI(title="CareerOps Copilot Backend")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "CareerOps Copilot Backend is running!"}

# Allow CORS for the Chrome Extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to extension ID or specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for incoming requests
class ChatRequest(BaseModel):
    message: str
    profile: str
    page_context: List[Dict[str, Any]]

class ChatResponse(BaseModel):
    reply: str
    tool_call: Optional[Dict[str, Any]] = None

# Initialize OpenAI client if key exists
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Handle chat messages from the extension.
    Uses LLM (if configured) to interpret the user's intent based on page context and profile.
    """
    if not client:
        # Fallback Mock logic if no OpenAI key is set
        print("No OPENAI_API_KEY set. Using mocked response.")
        
        # Simple heuristic matching for demonstration
        if "fill" in request.message.lower() and request.page_context:
            # Let's mock a fill action for the first input we find
            for el in request.page_context:
                if el.get('tagName') in ['input', 'textarea']:
                    return ChatResponse(
                        reply="I'm filling out the first input field I found as a demonstration.",
                        tool_call={
                            "type": "fill_input",
                            "selector": el.get('selector'),
                            "value": "Mocked value from profile"
                        }
                    )
            return ChatResponse(reply="I couldn't find any inputs to fill on this page.")
            
        elif "click" in request.message.lower() and request.page_context:
            for el in request.page_context:
                if el.get('tagName') in ['button', 'a']:
                    return ChatResponse(
                        reply="I clicked the first button I found as a demonstration.",
                        tool_call={
                            "type": "click",
                            "selector": el.get('selector')
                        }
                    )
                    
        return ChatResponse(reply=f"Mocked Backend Received: '{request.message}'. Set OPENAI_API_KEY to enable real AI.")

    # --- Real LLM Integration ---
    try:
        # Construct the System Prompt
        system_prompt = f"""
You are CareerOps Copilot, an AI browser agent. Your job is to help the user navigate websites, fill forms, and click buttons to achieve their goal.
You have access to the current page's interactive elements context.

User Profile:
{request.profile if request.profile else "None provided."}

Page Context (DOM Elements):
{json.dumps(request.page_context, indent=2)}

CRITICAL INSTRUCTIONS:
If the user's request implies interacting with the page (e.g., "Search for a hotel", "Book a flight", "Log in", "Fill this form"), YOU MUST output a JSON tool call at the very end of your response inside a markdown block. Do NOT just converse if an action can be taken on the page context provided.

Format the JSON block EXACTLY like this:
```json
{{"tool": {{"type": "fill_input", "selector": "#email", "value": "user@example.com"}}}}
```

Supported Tool Types:
1. `fill_input`: Requires `selector` and `value`.
2. `click`: Requires `selector`.
3. `scroll_page`: Requires `amount` (e.g. 500).

- You can only perform ONE action at a time. Pick the most logical first step (e.g., if they ask to book a hotel, first fill the 'destination' input or click the search box).
- Look closely at the Page Context to find the right `selector`. Match it by `text`, `tagName`, or `type`.
"""

        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ],
            temperature=0.0
        )

        reply_text = response.choices[0].message.content
        tool_call = None

        # Hacky tool-call parsing (in a real app, use OpenAI's Function Calling feature)
        if "```json" in reply_text:
            try:
                # Extract JSON block
                json_str = reply_text.split("```json")[1].split("```")[0].strip()
                parsed_json = json.loads(json_str)
                if "tool" in parsed_json:
                    tool_call = parsed_json["tool"]
                
                # Remove the JSON block from the reply text so it looks clean to the user
                reply_text = reply_text.split("```json")[0].strip()
            except Exception as e:
                print("Failed to parse tool call JSON:", e)

        return ChatResponse(reply=reply_text, tool_call=tool_call)

    except Exception as e:
        print("LLM Error:", e)
        raise HTTPException(status_code=500, detail=str(e))
