from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.routers import chat, autofill

load_dotenv()

app = FastAPI(title="CareerOps Copilot Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to chrome-extension://<id>
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(chat.router)
app.include_router(autofill.router)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "CareerOps Copilot Backend is running with LangChain & RAG!"}
