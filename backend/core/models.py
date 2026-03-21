"""
models.py — Shared Pydantic schemas used across agents and API layers.
Keeping models centralised prevents circular imports and ensures
a single source of truth for data contracts.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


# ── Query Intent ──────────────────────────────────────────────────────────────

class QueryIntent(str, Enum):
    QA            = "qa"            # Factual question answering
    SUMMARIZE     = "summarize"     # Summarise one or more documents
    COMPARE       = "compare"       # Compare two or more papers
    TREND         = "trend"         # Identify trends across documents
    GENERAL       = "general"       # Catch-all / unknown intent


# ── Document Chunk ────────────────────────────────────────────────────────────

class DocumentChunk(BaseModel):
    """A single chunk of text extracted from a PDF."""
    chunk_id:    str
    doc_id:      str                    # Filename / paper identifier
    text:        str
    page_number: Optional[int] = None
    metadata:    Dict[str, Any] = {}


# ── Retrieval Result ──────────────────────────────────────────────────────────

class RetrievalResult(BaseModel):
    """A retrieved chunk annotated with its relevance scores."""
    chunk:          DocumentChunk
    semantic_score: float = 0.0
    bm25_score:     float = 0.0
    hybrid_score:   float = 0.0         # Weighted combination


# ── API Request / Response schemas ───────────────────────────────────────────

class QueryRequest(BaseModel):
    question:    str  = Field(..., min_length=3, description="User question")
    doc_ids:     Optional[List[str]] = Field(None, description="Filter to specific papers")
    top_k:       int  = Field(5, ge=1, le=20)


class SummarizeRequest(BaseModel):
    doc_ids:     List[str] = Field(..., min_items=1, description="Papers to summarise")
    focus:       Optional[str] = Field(None, description="Optional focus area")


class CompareRequest(BaseModel):
    doc_ids:     List[str] = Field(..., min_items=2, max_items=5)
    aspects:     Optional[List[str]] = Field(None, description="Aspects to compare")


class AgentResponse(BaseModel):
    """Unified response envelope returned by all endpoints."""
    answer:       str
    intent:       QueryIntent
    sources:      List[RetrievalResult] = []
    doc_ids_used: List[str] = []
    confidence:   Optional[float] = None   # Set by Evaluation Agent
    reasoning:    Optional[str]  = None    # Reasoning Agent trace
    metadata:     Dict[str, Any] = {}


class UploadResponse(BaseModel):
    doc_id:       str
    filename:     str
    num_chunks:   int
    status:       str = "indexed"


class DocumentInfo(BaseModel):
    doc_id:    str
    filename:  str
    num_pages: int
    num_chunks: int
