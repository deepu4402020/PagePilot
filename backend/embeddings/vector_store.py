"""
PagePilot — Vector Store (Per-Tab RAG Pipeline)

Design decisions:
- Uses per-tab ChromaDB collections to isolate context and prevent cross-tab contamination
- Content hashing prevents duplicate embeddings when the same page is re-indexed
- Collections are cleaned up when tabs are closed or context is replaced
- Text is split with RecursiveCharacterTextSplitter (1000 chars, 200 overlap) 
  chosen to balance semantic coherence with retrieval granularity
"""

import hashlib
import logging
import os

import chromadb
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger("pagepilot.vector_store")

# Persistent storage directory
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", ".chromadb")
os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)

# Shared ChromaDB client singleton
_chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

# Shared embeddings model (lazy singleton — initialized on first use)
_embeddings = None

def _get_embeddings() -> OpenAIEmbeddings:
    """Lazy singleton for OpenAI embeddings. Avoids import-time API key requirements."""
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings()
    return _embeddings

# Text splitter configuration
# - chunk_size=1000: balances context completeness with retrieval precision
# - chunk_overlap=200: ensures important context isn't split across chunk boundaries
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    separators=["\n\n", "\n", ". ", ", ", " ", ""]
)

# In-memory cache: tracks which content has been indexed per tab
# Maps tab_id → content_hash to prevent duplicate embedding calls
_indexed_hashes: dict[int, str] = {}


def _get_collection_name(tab_id: int) -> str:
    """Returns a ChromaDB-safe collection name for a tab."""
    return f"tab_{tab_id}"


def _content_hash(text: str) -> str:
    """Returns a SHA-256 hash of the text for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def update_page_context(tab_id: int, page_text: str, url: str = "") -> bool:
    """
    Indexes page text into a per-tab ChromaDB collection.
    
    Deduplication: if the page content hasn't changed (same hash), 
    skip re-indexing to avoid duplicate embeddings and wasted API calls.
    
    Returns True if new content was indexed, False if skipped.
    """
    if not page_text or not page_text.strip():
        return False

    content_hash = _content_hash(page_text)

    # Skip if this exact content is already indexed for this tab
    if _indexed_hashes.get(tab_id) == content_hash:
        logger.debug(f"Tab {tab_id}: content unchanged, skipping re-index")
        return False

    try:
        collection_name = _get_collection_name(tab_id)

        # Delete old collection for this tab (replace, don't accumulate)
        try:
            _chroma_client.delete_collection(collection_name)
            logger.info(f"Tab {tab_id}: cleared old collection")
        except Exception:
            pass  # Collection may not exist yet

        # Split text into chunks
        chunks = text_splitter.split_text(page_text)
        if not chunks:
            return False

        # Create documents with metadata
        docs = [
            Document(
                page_content=chunk,
                metadata={
                    "tab_id": tab_id,
                    "url": url,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "content_hash": content_hash,
                }
            )
            for i, chunk in enumerate(chunks)
        ]

        # Index into per-tab collection
        Chroma.from_documents(
            documents=docs,
            embedding=_get_embeddings(),
            collection_name=collection_name,
            persist_directory=CHROMA_PERSIST_DIR,
        )

        # Update hash cache
        _indexed_hashes[tab_id] = content_hash
        logger.info(f"Tab {tab_id}: indexed {len(chunks)} chunks from {url or 'unknown URL'}")
        return True

    except Exception as e:
        logger.error(f"Tab {tab_id}: failed to index page content: {e}")
        return False


def get_relevant_context(query: str, tab_id: int, top_k: int = 4) -> str:
    """
    Retrieves the most relevant text chunks for a query from a specific tab's collection.
    
    Uses cosine similarity search (ChromaDB default) with per-tab isolation.
    Returns formatted context string or empty string if no results.
    """
    try:
        collection_name = _get_collection_name(tab_id)

        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=_get_embeddings(),
            persist_directory=CHROMA_PERSIST_DIR,
        )

        results = vector_store.similarity_search(
            query=query,
            k=top_k,
        )

        if not results:
            logger.debug(f"Tab {tab_id}: no relevant context found for query")
            return ""

        context = "\n\n".join([
            f"[Chunk {i+1}/{len(results)}]:\n{doc.page_content}"
            for i, doc in enumerate(results)
        ])

        logger.info(f"Tab {tab_id}: retrieved {len(results)} chunks for query")
        return context

    except Exception as e:
        logger.error(f"Tab {tab_id}: context retrieval failed: {e}")
        return ""


def clear_tab_context(tab_id: int) -> bool:
    """
    Removes all indexed content for a tab. 
    Called when a tab is closed or navigates to a new page.
    """
    try:
        collection_name = _get_collection_name(tab_id)
        _chroma_client.delete_collection(collection_name)
        _indexed_hashes.pop(tab_id, None)
        logger.info(f"Tab {tab_id}: context cleared")
        return True
    except Exception as e:
        logger.error(f"Tab {tab_id}: failed to clear context: {e}")
        return False
