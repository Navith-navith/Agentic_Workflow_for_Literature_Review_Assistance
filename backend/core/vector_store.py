"""
vector_store.py — Thin abstraction over FAISS / ChromaDB.

Why abstract?  Swapping the vector backend requires changing only
this file; all agents call the same interface.

Public API:
    get_store()           → VectorStore singleton
    store.add(chunks)     → index DocumentChunks
    store.search(query)   → return [(chunk, score), ...]
    store.delete(doc_id)  → remove all chunks for a document
    store.list_docs()     → returns distinct doc_ids indexed
"""
from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer

from core.config import settings
from core.models import DocumentChunk


# ─────────────────────────────────────────────────────────────────────────────
# Embedding helper (shared by both backends)
# ─────────────────────────────────────────────────────────────────────────────

class EmbeddingModel:
    """Wraps sentence-transformers; caches the model as a module-level singleton."""
    _instance: Optional[EmbeddingModel] = None

    def __init__(self):
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        self.model = SentenceTransformer(settings.embedding_model)
        self.dim   = self.model.get_sentence_embedding_dimension()

    @classmethod
    def get(cls) -> "EmbeddingModel":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def encode(self, texts: List[str]) -> np.ndarray:
        """Return L2-normalised float32 embeddings."""
        vecs = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return (vecs / norms).astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# Base interface
# ─────────────────────────────────────────────────────────────────────────────

class VectorStore:
    def add(self, chunks: List[DocumentChunk]) -> None:
        raise NotImplementedError

    def search(self, query: str, top_k: int = 5, doc_ids: Optional[List[str]] = None) -> List[Tuple[DocumentChunk, float]]:
        raise NotImplementedError

    def delete(self, doc_id: str) -> None:
        raise NotImplementedError

    def list_docs(self) -> List[str]:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# FAISS implementation
# ─────────────────────────────────────────────────────────────────────────────

class FAISSVectorStore(VectorStore):
    """
    Pure-Python FAISS store.  Metadata is stored in a parallel pickle list
    so we can filter by doc_id post-retrieval.
    """

    _INDEX_FILE = "faiss.index"
    _META_FILE  = "faiss_meta.pkl"

    def __init__(self):
        import faiss
        self.faiss  = faiss
        self._emb   = EmbeddingModel.get()
        self._dir   = Path(settings.vector_store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

        idx_path  = self._dir / self._INDEX_FILE
        meta_path = self._dir / self._META_FILE

        if idx_path.exists() and meta_path.exists():
            self._index = faiss.read_index(str(idx_path))
            with open(meta_path, "rb") as f:
                self._meta: List[DocumentChunk] = pickle.load(f)
            logger.info(f"FAISS: loaded {self._index.ntotal} vectors")
        else:
            self._index = faiss.IndexFlatIP(self._emb.dim)  # Inner product = cosine on normalised vecs
            self._meta  = []
            logger.info("FAISS: initialised fresh index")

    def _save(self):
        self.faiss.write_index(self._index, str(self._dir / self._INDEX_FILE))
        with open(self._dir / self._META_FILE, "wb") as f:
            pickle.dump(self._meta, f)

    def add(self, chunks: List[DocumentChunk]) -> None:
        texts = [c.text for c in chunks]
        vecs  = self._emb.encode(texts)
        self._index.add(vecs)
        self._meta.extend(chunks)
        self._save()
        logger.info(f"FAISS: added {len(chunks)} chunks (total={self._index.ntotal})")

    def search(self, query: str, top_k: int = 5, doc_ids: Optional[List[str]] = None) -> List[Tuple[DocumentChunk, float]]:
        if self._index.ntotal == 0:
            return []
        q_vec = self._emb.encode([query])
        k     = min(top_k * 4, self._index.ntotal)   # Over-fetch then filter
        scores, idxs = self._index.search(q_vec, k)

        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0 or idx >= len(self._meta):
                continue
            chunk = self._meta[idx]
            if doc_ids and chunk.doc_id not in doc_ids:
                continue
            results.append((chunk, float(score)))
            if len(results) >= top_k:
                break
        return results

    def delete(self, doc_id: str) -> None:
        # FAISS FlatIndex doesn't support deletion natively; rebuild without target.
        kept_chunks = [c for c in self._meta if c.doc_id != doc_id]
        import faiss
        self._index = faiss.IndexFlatIP(self._emb.dim)
        self._meta  = []
        if kept_chunks:
            self.add(kept_chunks)
        else:
            self._save()
        logger.info(f"FAISS: deleted chunks for doc_id={doc_id}")

    def list_docs(self) -> List[str]:
        return list({c.doc_id for c in self._meta})


# ─────────────────────────────────────────────────────────────────────────────
# ChromaDB implementation
# ─────────────────────────────────────────────────────────────────────────────

class ChromaVectorStore(VectorStore):
    """Uses ChromaDB with a local persistent client."""

    def __init__(self):
        import chromadb
        self._emb    = EmbeddingModel.get()
        self._client = chromadb.PersistentClient(path=settings.vector_store_dir)
        self._col    = self._client.get_or_create_collection(
            name="healthcare_rag",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB: collection has {self._col.count()} items")

    def add(self, chunks: List[DocumentChunk]) -> None:
        texts   = [c.text for c in chunks]
        vecs    = self._emb.encode(texts).tolist()
        ids     = [c.chunk_id for c in chunks]
        metas   = [{"doc_id": c.doc_id, "page": c.page_number or 0} for c in chunks]
        self._col.add(embeddings=vecs, documents=texts, ids=ids, metadatas=metas)
        logger.info(f"ChromaDB: added {len(chunks)} chunks")

    def search(self, query: str, top_k: int = 5, doc_ids: Optional[List[str]] = None) -> List[Tuple[DocumentChunk, float]]:
        q_vec = self._emb.encode([query]).tolist()
        where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
        res   = self._col.query(
            query_embeddings=q_vec,
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        results = []
        for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            chunk = DocumentChunk(
                chunk_id    = meta.get("id", ""),
                doc_id      = meta["doc_id"],
                text        = text,
                page_number = meta.get("page"),
            )
            score = 1.0 - dist   # Chroma returns cosine distance; convert to similarity
            results.append((chunk, score))
        return results

    def delete(self, doc_id: str) -> None:
        self._col.delete(where={"doc_id": doc_id})
        logger.info(f"ChromaDB: deleted chunks for doc_id={doc_id}")

    def list_docs(self) -> List[str]:
        all_meta = self._col.get(include=["metadatas"])["metadatas"]
        return list({m["doc_id"] for m in all_meta})


# ─────────────────────────────────────────────────────────────────────────────
# Factory / Singleton
# ─────────────────────────────────────────────────────────────────────────────

_store: Optional[VectorStore] = None


def get_store() -> VectorStore:
    """Return the configured VectorStore singleton."""
    global _store
    if _store is None:
        if settings.vector_store_type == "chroma":
            _store = ChromaVectorStore()
        else:
            _store = FAISSVectorStore()
    return _store
