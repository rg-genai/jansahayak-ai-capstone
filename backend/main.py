"""JanSahayak AI FastAPI Server Entrypoint (Single Worker for Track B Concurrency Safety)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_auth import router as auth_router
from backend.api.routes_chat import router as chat_router
from backend.api.routes_observability import router as observability_router
from backend.api.routes_schemes import router as schemes_router
from backend.api.routes_voice import router as voice_router
from backend.config import get_settings
from backend.db.database import init_db
from backend.retrieval.hybrid_retriever import get_hybrid_retriever
from backend.services.mock_cpgrams_router import router as mock_cpgrams_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jansahayak.main")


def _prewarm_retrieval_stack() -> None:
    """Load embeddings.npy, bm25.pkl, and CPU CrossEncoder in background so first chat turn is fast."""
    try:
        retriever = get_hybrid_retriever()
        retriever._get_reranker()
        logger.info("HybridRetriever & CrossEncoder pre-warmed and ready.")
    except Exception as exc:
        logger.warning("Background pre-warm skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(settings.db_abs_path)
    # Kick off non-blocking background pre-warm of HybridRetriever + CrossEncoder
    asyncio.create_task(asyncio.to_thread(_prewarm_retrieval_stack))
    logger.info(
        "JanSahayak AI started | LLM=%s | Embeddings=%s | Mode=%s",
        settings.llm_model,
        settings.embedding_model,
        settings.grievance_mode,
    )
    yield
    logger.info("JanSahayak AI shutting down.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="JanSahayak AI — Multilingual Indian Welfare Scheme & CPGRAMS Copilot",
        version="1.1.0",
        description="IIT Kharagpur GenAI & Agentic AI Track B Capstone Project",
        lifespan=lifespan,
    )

    origins = list(
        {
            settings.frontend_origin,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "http://localhost:3000",
        }
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(observability_router)
    app.include_router(chat_router)
    app.include_router(schemes_router)
    app.include_router(voice_router)
    app.include_router(mock_cpgrams_router)

    @app.get("/")
    async def root():
        return {
            "service": "JanSahayak AI",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
