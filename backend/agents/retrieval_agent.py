"""
retrieval_agent.py — Hybrid retrieval: semantic (dense) + BM25 (sparse).

Pipeline:
  1. Semantic search  → vector similarity via VectorStore
  2. BM25 search      → keyword match via rank-bm25
  3. Reciprocal Rank Fusion (RRF) + configurable alpha blend → ranked list

Why hybrid?
  Dense vectors capture semantics but miss exact keyword matches.
  BM25 catches exact terms but ignores paraphrase.
  Fusion gives the best of both worlds — standard in production RAG.
"""
from __future__ import annotations

import math
from typing import List, Optional, Dict

import nltk
from loguru import logger
from rank_bm25 import BM25Okapi

from core.config import settings
from core.models import DocumentChunk, RetrievalResult
from core.vector_store import get_store

# ── NLTK bootstrap ────────────────────────────────────────────────────────────
# NLTK 3.9+ requires 'punkt_tab' instead of (or alongside) 'punkt'.
# We attempt each package and download only if missing — safe to run multiple times.
def _ensure_nltk():
    packages = {
        "punkt":     "tokenizers/punkt",
        "punkt_tab": "tokenizers/punkt_tab",
        "stopwords": "corpora/stopwords",
    }
    for pkg, path in packages.items():
        try:
            nltk.data.find(path)
        except LookupError:
            try:
                nltk.download(pkg, quiet=True)
            except Exception:
                pass  # Offline or already present under a different path

_ensure_nltk()

from nltk.corpus import stopwords as _sw
from nltk.tokenize import word_tokenize

_STOPWORDS = set(_sw.words("english"))


def _tokenize(text: str) -> List[str]:
    """Lowercase tokenisation with stopword removal for BM25."""
    try:
        tokens = word_tokenize(text.lower())
    except Exception:
        # Fallback if punkt_tab is still missing (e.g. fully offline)
        tokens = text.lower().split()
    return [t for t in tokens if t.isalnum() and t not in _STOPWORDS]


def _reciprocal_rank_fusion(
    ranked_lists: List[List[str]],    # Each list: chunk_ids in rank order
    k: int = 60,
) -> Dict[str, float]:
    """
    RRF score = Σ 1/(k + rank_i) across all lists.
    Higher is better.  k=60 is the standard recommendation (Cormack et al., 2009).
    """
    scores: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


class RetrievalAgent:
    """
    Performs hybrid retrieval over the indexed corpus.

    State:
      _bm25_index   — rebuilt whenever new chunks are added
      _bm25_chunks  — parallel list to _bm25_index rows
    """

    def __init__(self):
        self._store        = get_store()
        self._bm25_index   = None
        self._bm25_chunks: List[DocumentChunk] = []
        self._alpha        = settings.hybrid_alpha   # Weight for semantic vs BM25

    # ── Public API ────────────────────────────────────────────────────────────

    def index_chunks(self, chunks: List[DocumentChunk]) -> None:
        """
        Add chunks to the vector store AND rebuild the BM25 index.
        Called by the Document Agent after chunking a new PDF.
        """
        # Vector store indexing
        self._store.add(chunks)

        # Rebuild BM25 (re-tokenise all chunks — necessary because BM25Okapi
        # requires the full corpus at construction time)
        self._bm25_chunks.extend(chunks)
        tokenised = [_tokenize(c.text) for c in self._bm25_chunks]
        self._bm25_index = BM25Okapi(tokenised)
        logger.info(f"RetrievalAgent: BM25 index rebuilt with {len(self._bm25_chunks)} chunks")

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        doc_ids: Optional[List[str]] = None,
    ) -> List[RetrievalResult]:
        """
        Main retrieval entry point.  Returns hybrid-ranked RetrievalResult list.

        Args:
            query:   User query (or refined query from ReasoningAgent).
            top_k:   Number of results to return.
            doc_ids: Optional list of doc_ids to constrain retrieval.
        """
        if not self._bm25_chunks:
            logger.warning("RetrievalAgent: no chunks indexed yet")
            return []

        semantic_results = self._semantic_search(query, top_k=settings.top_k_semantic, doc_ids=doc_ids)
        bm25_results     = self._bm25_search(query, top_k=settings.top_k_bm25, doc_ids=doc_ids)

        fused = self._fuse(semantic_results, bm25_results, top_k=top_k)
        logger.info(f"RetrievalAgent: retrieved {len(fused)} results for query='{query[:60]}'")
        return fused

    # ── Private: Semantic search ──────────────────────────────────────────────

    def _semantic_search(
        self, query: str, top_k: int, doc_ids: Optional[List[str]]
    ) -> List[tuple]:
        """Dense vector search via the VectorStore."""
        return self._store.search(query, top_k=top_k, doc_ids=doc_ids)

    # ── Private: BM25 search ──────────────────────────────────────────────────

    def _bm25_search(
        self, query: str, top_k: int, doc_ids: Optional[List[str]]
    ) -> List[tuple]:
        """Sparse keyword search using BM25Okapi."""
        if self._bm25_index is None:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        raw_scores = self._bm25_index.get_scores(tokens)   # ndarray, one score per chunk

        # Filter by doc_ids if requested
        scored = []
        for i, chunk in enumerate(self._bm25_chunks):
            if doc_ids and chunk.doc_id not in doc_ids:
                continue
            scored.append((chunk, float(raw_scores[i])))

        # Sort descending, return top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ── Private: Fusion ───────────────────────────────────────────────────────

    def _fuse(
        self,
        semantic: List[tuple],
        bm25:     List[tuple],
        top_k:    int,
    ) -> List[RetrievalResult]:
        """
        Combine semantic and BM25 results using Reciprocal Rank Fusion,
        then re-score with an alpha-weighted blend for final ranking.
        """
        # Build chunk lookup maps
        sem_map  = {c.chunk_id: (c, s) for c, s in semantic}
        bm25_map = {c.chunk_id: (c, s) for c, s in bm25}

        # RRF on rank lists
        rrf_scores = _reciprocal_rank_fusion(
            [list(sem_map.keys()), list(bm25_map.keys())]
        )

        # Normalise raw scores to [0, 1] within each list
        sem_scores  = {cid: s for cid, (_, s) in sem_map.items()}
        bm25_scores = {cid: s for cid, (_, s) in bm25_map.items()}

        def _norm(scores: Dict[str, float]) -> Dict[str, float]:
            if not scores:
                return {}
            mx = max(scores.values()) or 1.0
            return {k: v / mx for k, v in scores.items()}

        sem_norm  = _norm(sem_scores)
        bm25_norm = _norm(bm25_scores)

        # Merge all unique chunk IDs
        all_ids = set(sem_map) | set(bm25_map)

        results: List[RetrievalResult] = []
        for cid in all_ids:
            chunk = (sem_map.get(cid) or bm25_map.get(cid))[0]
            s_sem  = sem_norm.get(cid, 0.0)
            s_bm25 = bm25_norm.get(cid, 0.0)

            # Alpha-weighted hybrid score
            hybrid = self._alpha * s_sem + (1.0 - self._alpha) * s_bm25

            results.append(RetrievalResult(
                chunk          = chunk,
                semantic_score = s_sem,
                bm25_score     = s_bm25,
                hybrid_score   = hybrid,
            ))

        # Sort by hybrid score descending
        results.sort(key=lambda r: r.hybrid_score, reverse=True)
        return results[:top_k]
