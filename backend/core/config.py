"""
config.py — Centralised settings loaded from .env
All modules import from here; never hard-code values elsewhere.
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────
    groq_api_key: str = ""
    llm_model: str = "llama3-70b-8192"

    # ── Embeddings & Vector Store ─────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    vector_store_type: str = "faiss"       # "faiss" | "chroma"
    vector_store_dir: str = "./data/vector_store"

    # ── File Storage ──────────────────────────────────────────
    upload_dir: str = "./data/uploads"

    # ── Chunking ──────────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 64

    # ── Retrieval ─────────────────────────────────────────────
    top_k_semantic: int = 5
    top_k_bm25: int = 5
    hybrid_alpha: float = 0.6              # 1.0 = pure semantic, 0.0 = pure BM25

    # ── API ───────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton — import `settings` everywhere
settings = Settings()

# Ensure data directories exist at startup
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.vector_store_dir, exist_ok=True)
