"""
document_agent.py — Owns the lifecycle of uploaded documents.

Responsibilities:
  1. Receive a PDF file path from the API layer
  2. Extract + clean text (via pdf_processor utility)
  3. Create DocumentChunk objects with unique IDs
  4. Delegate indexing to the RetrievalAgent
  5. Maintain a lightweight in-memory registry of processed documents

This agent is the single gateway for all document ingestion — no other
component writes to the vector store or manipulates chunks directly.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Dict, Optional

from loguru import logger

from core.config import settings
from core.models import DocumentChunk, DocumentInfo
from utils.pdf_processor import extract_pages, chunk_pages


class DocumentAgent:
    """
    Processes PDFs and maintains a registry of indexed documents.

    The registry (self._registry) is in-memory for simplicity.
    In production this would be backed by a database (PostgreSQL / SQLite).
    """

    def __init__(self, retrieval_agent):
        """
        Args:
            retrieval_agent: RetrievalAgent instance — called to index chunks.
        """
        self._retrieval_agent = retrieval_agent

        # doc_id → DocumentInfo
        self._registry: Dict[str, DocumentInfo] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def process_pdf(self, file_path: str, original_filename: str) -> DocumentInfo:
        """
        Full ingestion pipeline for a single PDF.

        Returns:
            DocumentInfo with chunk count and page count.

        Raises:
            ValueError: if file is unreadable or produces no text.
        """
        doc_id = original_filename   # Use filename as the stable identifier
        logger.info(f"DocumentAgent: ingesting '{original_filename}'")

        # ── 1. Extract pages ──────────────────────────────────
        pages = extract_pages(file_path)
        if not pages:
            raise ValueError(f"No extractable text found in '{original_filename}'")

        num_pages = max(p for p, _ in pages)

        # ── 2. Chunk pages ────────────────────────────────────
        raw_chunks = chunk_pages(
            pages,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
        if not raw_chunks:
            raise ValueError(f"Chunking produced no output for '{original_filename}'")

        # ── 3. Build DocumentChunk objects ────────────────────
        chunks: List[DocumentChunk] = []
        for page_num, text in raw_chunks:
            chunk = DocumentChunk(
                chunk_id    = str(uuid.uuid4()),
                doc_id      = doc_id,
                text        = text,
                page_number = page_num,
                metadata    = {"source": original_filename},
            )
            chunks.append(chunk)

        # ── 4. Index via RetrievalAgent ───────────────────────
        self._retrieval_agent.index_chunks(chunks)

        # ── 5. Register document ──────────────────────────────
        info = DocumentInfo(
            doc_id     = doc_id,
            filename   = original_filename,
            num_pages  = num_pages,
            num_chunks = len(chunks),
        )
        self._registry[doc_id] = info
        logger.info(
            f"DocumentAgent: '{original_filename}' → {num_pages} pages, {len(chunks)} chunks"
        )
        return info

    def get_chunks_for_doc(self, doc_id: str) -> List[DocumentChunk]:
        """
        Retrieve all chunks belonging to a document from the vector store's
        metadata.  Used by the Answer Generation Agent for full-document ops
        like summarisation.
        """
        # Access the retrieval agent's BM25 chunk list directly for full coverage
        return [
            c for c in self._retrieval_agent._bm25_chunks
            if c.doc_id == doc_id
        ]

    def list_documents(self) -> List[DocumentInfo]:
        """Return all registered documents."""
        return list(self._registry.values())

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        return self._registry.get(doc_id)

    def delete_document(self, doc_id: str) -> bool:
        """Remove document from vector store and registry."""
        if doc_id not in self._registry:
            return False
        self._retrieval_agent._store.delete(doc_id)
        # Also remove from BM25 corpus and rebuild
        self._retrieval_agent._bm25_chunks = [
            c for c in self._retrieval_agent._bm25_chunks if c.doc_id != doc_id
        ]
        if self._retrieval_agent._bm25_chunks:
            from agents.retrieval_agent import _tokenize
            from rank_bm25 import BM25Okapi
            tokenised = [_tokenize(c.text) for c in self._retrieval_agent._bm25_chunks]
            self._retrieval_agent._bm25_index = BM25Okapi(tokenised)
        else:
            self._retrieval_agent._bm25_index = None

        del self._registry[doc_id]
        logger.info(f"DocumentAgent: deleted '{doc_id}'")
        return True

    def available_doc_ids(self) -> List[str]:
        return list(self._registry.keys())
