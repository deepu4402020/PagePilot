from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os

# Initialize in-memory/local ChromaDB
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", ".chromadb")
os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)

embeddings = OpenAIEmbeddings()
vector_store = Chroma(
    collection_name="page_content",
    embedding_function=embeddings,
    persist_directory=CHROMA_PERSIST_DIR
)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len
)

def update_page_context(tab_id: int, page_text: str, url: str = ""):
    """Chunks the new page text and stores it in ChromaDB, tagged by tab_id."""
    if not page_text:
        return
        
    # Optional: Delete old context for this tab to prevent memory bloat
    # (Chroma doesn't easily support delete by metadata in the basic wrapper, 
    # but we can filter during retrieval)
    
    chunks = text_splitter.split_text(page_text)
    docs = [
        Document(
            page_content=chunk, 
            metadata={"tab_id": tab_id, "url": url, "chunk_index": i}
        ) 
        for i, chunk in enumerate(chunks)
    ]
    
    vector_store.add_documents(docs)

def get_relevant_context(query: str, tab_id: int, top_k: int = 3) -> str:
    """Retrieves relevant chunks for a specific tab."""
    results = vector_store.similarity_search(
        query=query,
        k=top_k,
        filter={"tab_id": tab_id}
    )
    
    if not results:
        return ""
        
    return "\n\n".join([f"Context Chunk {i+1}:\n{doc.page_content}" for i, doc in enumerate(results)])
