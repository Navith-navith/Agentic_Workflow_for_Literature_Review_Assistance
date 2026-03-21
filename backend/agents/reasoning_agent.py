"""
reasoning_agent.py — Understands WHAT the user wants before retrieval.

Responsibilities:
  1. Classify query intent: QA | SUMMARIZE | COMPARE | TREND | GENERAL
  2. Extract key entities (paper names, topics, aspects to compare)
  3. Produce a structured ReasoningPlan consumed by downstream agents

Design choice: Uses a lightweight rule-based classifier as the primary path
(fast, free, deterministic) with an optional LLM fallback for ambiguous cases.
This keeps latency low for common patterns.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from loguru import logger

from core.models import QueryIntent


# ─────────────────────────────────────────────────────────────────────────────
# Data structures produced by this agent
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ReasoningPlan:
    """
    Structured output of the Reasoning Agent.
    Passed downstream to Retrieval and Answer Generation agents.
    """
    intent:          QueryIntent
    refined_query:   str                    # Cleaned / expanded query for retrieval
    target_doc_ids:  List[str]  = field(default_factory=list)   # Specific papers mentioned
    aspects:         List[str]  = field(default_factory=list)   # Comparison dimensions
    focus_topic:     Optional[str] = None   # E.g. "drug delivery" for trend queries
    reasoning_trace: str = ""               # Human-readable explanation of classification


# ─────────────────────────────────────────────────────────────────────────────
# Keyword patterns for rule-based intent classification
# ─────────────────────────────────────────────────────────────────────────────

_SUMMARIZE_PATTERNS = re.compile(
    r"\b(summar(ize|ise|y)|overview|abstract|brief|tldr|gist|outline)\b", re.I
)
_COMPARE_PATTERNS = re.compile(
    r"\b(compar(e|ing|ison)|differ(ence|ent)|versus|vs\.?|contrast|between)\b", re.I
)
_TREND_PATTERNS = re.compile(
    r"\b(trend|pattern|develop(ment|ing)|emerg(e|ing|ence)|evolution|progress|advance)\b", re.I
)


# ─────────────────────────────────────────────────────────────────────────────
# Agent class
# ─────────────────────────────────────────────────────────────────────────────

class ReasoningAgent:
    """
    Classifies intent and builds a structured ReasoningPlan.

    The agent is intentionally stateless — each call to `plan()` is
    independent, making it safe to share across concurrent requests.
    """

    def __init__(self, available_doc_ids: Optional[List[str]] = None):
        """
        Args:
            available_doc_ids: Doc IDs currently indexed; used to detect
                               paper references in the query.
        """
        self.available_doc_ids = available_doc_ids or []

    def plan(self, query: str) -> ReasoningPlan:
        """
        Analyse the query and return a ReasoningPlan.

        Steps:
          1. Detect explicit paper references in the query.
          2. Classify intent via regex patterns.
          3. Extract aspects for COMPARE intents.
          4. Refine the query string for downstream retrieval.
        """
        logger.info(f"ReasoningAgent: analysing query='{query[:80]}...'")

        # ── Step 1: Detect referenced papers ─────────────────
        target_docs = self._detect_paper_references(query)

        # ── Step 2: Classify intent ───────────────────────────
        intent, trace = self._classify_intent(query, target_docs)

        # ── Step 3: Extract comparison aspects ───────────────
        aspects = []
        if intent == QueryIntent.COMPARE:
            aspects = self._extract_aspects(query)

        # ── Step 4: Extract trend topic ───────────────────────
        focus_topic = None
        if intent == QueryIntent.TREND:
            focus_topic = self._extract_focus_topic(query)

        # ── Step 5: Refine query for retrieval ────────────────
        refined = self._refine_query(query, intent, aspects)

        plan = ReasoningPlan(
            intent          = intent,
            refined_query   = refined,
            target_doc_ids  = target_docs,
            aspects         = aspects,
            focus_topic     = focus_topic,
            reasoning_trace = trace,
        )
        logger.info(f"ReasoningAgent: intent={intent}, docs={target_docs}, aspects={aspects}")
        return plan

    # ── Private helpers ───────────────────────────────────────────────────────

    def _detect_paper_references(self, query: str) -> List[str]:
        """
        Check if the query mentions any indexed document by name.
        Matching is case-insensitive and partial (filename stem).
        """
        q_lower = query.lower()
        matched = []
        for doc_id in self.available_doc_ids:
            # Match on filename stem (strip extension)
            stem = doc_id.rsplit(".", 1)[0].lower().replace("_", " ")
            if stem in q_lower or doc_id.lower() in q_lower:
                matched.append(doc_id)
        return matched

    def _classify_intent(self, query: str, target_docs: List[str]) -> tuple[QueryIntent, str]:
        """Rule-based intent classification with confidence trace."""

        if _COMPARE_PATTERNS.search(query):
            return QueryIntent.COMPARE, "Detected comparison keywords (compare/versus/contrast)"

        if _SUMMARIZE_PATTERNS.search(query):
            return QueryIntent.SUMMARIZE, "Detected summarisation keywords (summarize/overview/brief)"

        if _TREND_PATTERNS.search(query):
            return QueryIntent.TREND, "Detected trend keywords (trend/emerging/evolution)"

        # Heuristic: short questions without WH-words tend to be general
        wh_words = re.compile(r"\b(what|how|why|when|where|who|which|explain|describe)\b", re.I)
        if wh_words.search(query):
            return QueryIntent.QA, "Detected WH-question → factual QA"

        return QueryIntent.GENERAL, "No specific pattern matched → general intent"

    def _extract_aspects(self, query: str) -> List[str]:
        """
        Extract comparison dimensions mentioned in the query.
        E.g. "compare methodology and results" → ["methodology", "results"]
        """
        # Common academic comparison dimensions
        candidates = [
            "methodology", "method", "results", "findings", "accuracy",
            "performance", "dataset", "approach", "limitation", "contribution",
            "conclusion", "algorithm", "model", "architecture", "evaluation",
        ]
        q_lower = query.lower()
        return [a for a in candidates if a in q_lower] or ["methodology", "results", "findings"]

    def _extract_focus_topic(self, query: str) -> Optional[str]:
        """Extract the noun phrase following 'in X' or 'about X' for trend queries."""
        match = re.search(r"\b(?:in|about|regarding|on)\s+([a-zA-Z][a-zA-Z\s]{2,30})", query, re.I)
        if match:
            return match.group(1).strip()
        return None

    def _refine_query(self, query: str, intent: QueryIntent, aspects: List[str]) -> str:
        """
        Produce a retrieval-optimised version of the query.
        For COMPARE intents, append the aspect list to broaden coverage.
        """
        refined = query.strip()

        if intent == QueryIntent.COMPARE and aspects:
            aspect_str = " ".join(aspects[:3])
            refined    = f"{refined} {aspect_str}"

        if intent == QueryIntent.SUMMARIZE:
            # Retrieval needs broad coverage — add generic expansion
            refined = f"main contributions findings methodology {refined}"

        return refined
