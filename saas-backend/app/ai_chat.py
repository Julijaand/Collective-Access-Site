"""
AI Chat endpoint — RAG-powered support chatbot
Uses ChromaDB (vector search) + Ollama (LLM) + sentence-transformers (embeddings)
"""
from pathlib import Path
from typing import Optional, AsyncGenerator
import os
import json
import asyncio
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .database import get_db
from .auth import get_current_user
from .models import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ai"])

# Paths — relative to saas-backend/ root
AI_DIR = Path(__file__).parent.parent / "ai"
VECTOR_DB_PATH = AI_DIR / "vector_db"
COLLECTION_NAME = "ca_knowledge"

# In-cluster: http://ollama-svc:11434  |  Local dev: http://localhost:11434
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama-svc:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ── Pre-load at startup (avoids cold-start timeout on first request) ─────────
_embedding = None
_vector_store = None
_llm = None

try:
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    from langchain_ollama import OllamaLLM

    logger.info("Loading embedding model...")
    _embedding = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

    if VECTOR_DB_PATH.exists():
        _vector_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=_embedding,
            persist_directory=str(VECTOR_DB_PATH),
        )
        logger.info(f"Vector store loaded ({VECTOR_DB_PATH})")

    _llm = OllamaLLM(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.3,
        request_timeout=120.0,  # 2 min — allows model cold-start load time
    )
    logger.info(f"Ollama LLM ready ({OLLAMA_MODEL} @ {OLLAMA_BASE_URL})")
except Exception as _e:
    logger.warning(f"AI startup init failed (will retry on first request): {_e}")
# ─────────────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    tenant_id: Optional[int] = None


class ChatSource(BaseModel):
    title: str
    section: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[ChatSource]
    used_rag: bool


def _get_vector_store():
    """Return the pre-loaded vector store singleton (or None if not ready)."""
    global _vector_store, _embedding
    if _vector_store is not None:
        return _vector_store
    # Fallback: try loading now (e.g. ingest ran after startup)
    try:
        from langchain_chroma import Chroma
        if _embedding and VECTOR_DB_PATH.exists():
            _vector_store = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=_embedding,
                persist_directory=str(VECTOR_DB_PATH),
            )
            return _vector_store
    except Exception as e:
        logger.warning(f"Could not load vector store: {e}")
    return None


def _call_ollama(prompt: str) -> str:
    """Call Ollama LLM using the pre-loaded singleton."""
    global _llm
    if _llm is None:
        from langchain_ollama import OllamaLLM
        _llm = OllamaLLM(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.3, request_timeout=120.0)
    return _llm.invoke(prompt).strip()


def _build_prompt(question: str, context: str) -> str:
    return f"""You are a helpful support assistant for Collective Access, an open-source collections management software.
You help users of our SaaS platform manage their Collective Access instances.

Use the following knowledge base context to answer the user's question.
If the context does not contain enough information, answer from your general knowledge about Collective Access.
Be concise and friendly. Use markdown formatting when helpful.

--- CONTEXT ---
{context}
--- END CONTEXT ---

User question: {question}

Answer:"""


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    RAG-powered chat endpoint.
    1. Embed the user question
    2. Retrieve top-3 relevant chunks from ChromaDB
    3. Build a prompt with context
    4. Call Ollama for the answer
    5. Return reply + source references
    """
    question = request.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    sources: list[ChatSource] = []
    context = ""
    used_rag = False

    # --- Step 1: RAG retrieval ---
    vector_store = _get_vector_store()
    if vector_store:
        try:
            results = vector_store.similarity_search_with_score(question, k=3)
            chunks = []
            for doc, score in results:
                if score < 1.5:  # relevance threshold (lower = more similar in L2)
                    chunks.append(doc.page_content)
                    sources.append(ChatSource(
                        title=doc.metadata.get("title", "Knowledge Base"),
                        section=doc.metadata.get("section", ""),
                    ))
            if chunks:
                context = "\n\n".join(chunks)
                used_rag = True
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")

    # --- Step 2: Build prompt & call Ollama ---
    try:
        import asyncio
        prompt = _build_prompt(question, context)
        # Run blocking LLM call in a thread so it doesn't block the async event loop
        reply = await asyncio.get_event_loop().run_in_executor(None, _call_ollama, prompt)
    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="AI service unavailable. Make sure Ollama is running: `ollama serve`",
        )

    return ChatResponse(reply=reply, sources=sources, used_rag=used_rag)


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Streaming SSE chat endpoint — tokens are sent as they are generated.
    Frontend receives `data: {"token": "..."}` lines, then `data: {"done": true, "sources": [...]}`
    """
    question = request.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    sources: list[ChatSource] = []
    context = ""
    used_rag = False

    # RAG retrieval (same as non-streaming endpoint)
    vector_store = _get_vector_store()
    if vector_store:
        try:
            results = vector_store.similarity_search_with_score(question, k=3)
            chunks = []
            for doc, score in results:
                if score < 1.5:
                    chunks.append(doc.page_content)
                    sources.append(ChatSource(
                        title=doc.metadata.get("title", "Knowledge Base"),
                        section=doc.metadata.get("section", ""),
                    ))
            if chunks:
                context = "\n\n".join(chunks)
                used_rag = True
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")

    prompt = _build_prompt(question, context)

    async def token_generator() -> AsyncGenerator[str, None]:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = data.get("response", "")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        if data.get("done"):
                            yield f"data: {json.dumps({'done': True, 'sources': [s.dict() for s in sources], 'used_rag': used_rag})}\n\n"
                            return
        except Exception as e:
            logger.error(f"Streaming Ollama call failed: {e}")
            yield f"data: {json.dumps({'error': 'AI service unavailable'})}\n\n"

    return StreamingResponse(
        token_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


@router.get("/chat/health")
async def chat_health():
    """Check if Ollama is reachable and vector DB is ready."""
    ollama_ok = False
    vector_db_ready = VECTOR_DB_PATH.exists()

    try:
        import httpx
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        ollama_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "ollama": "ok" if ollama_ok else "unreachable — run `ollama serve`",
        "ollama_url": OLLAMA_BASE_URL,
        "ollama_model": OLLAMA_MODEL,
        "vector_db": "ready" if vector_db_ready else "not ingested — run ai/ingest.py",
        "vector_db_path": str(VECTOR_DB_PATH),
    }
