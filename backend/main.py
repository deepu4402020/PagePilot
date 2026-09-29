"""
PagePilot — FastAPI Backend Entry Point
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Ensure project root is in sys.path for 'from backend...' imports
_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

# CRITICAL: load_dotenv MUST run before any imports that use the OpenAI API key.
# The router imports trigger module-level OpenAIEmbeddings() initialization.
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import chat, autofill


# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pagepilot")

app = FastAPI(
    title="PagePilot Backend",
    description="AI-powered browser automation, webpage RAG, and intelligent form filling.",
    version="1.0.0",
)

# CORS: Restrict to Chrome extension origin in production
# In development, allow localhost origins for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "chrome-extension://*",     # Chrome extension origin
        "http://localhost:*",       # Dev server
        "http://127.0.0.1:*",      # Dev server alt
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Include Routers
app.include_router(chat.router)
app.include_router(autofill.router)


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "PagePilot",
        "version": "1.0.0",
    }
