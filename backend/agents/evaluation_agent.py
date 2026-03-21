"""
evaluation_agent.py — Optional post-hoc quality validation.

Responsibilities:
  1. Check answer groundedness: does it cite claims supported by the retrieved context?
  2. Check completeness: does it address the user's question?
  3. Return a confidence score (0–1) and optional warnings

Design notes:
  - Runs as a lightweight heuristic check (fast, deterministic).
  - Can optionally call the LLM for a more nuanced faithfulness score.
  - Results are appended to AgentResponse.confidence and AgentResponse.metadata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from loguru import logger

from core.models import RetrievalResult


@dataclass
class EvaluationResult:
    confidence: float        # 0.0 – 1.0
    is_grounded: bool        # True if answer appears backed by context
    is_complete: bool        # True if answer is non-trivially long
    warnings:    List[str]   # Human-readable quality issues


class EvaluationAgent:
    """
    Validates generated answers for quality before returning to the user.

    Metrics:
    ─────────────────────────────────────────────────────────
    Groundedness  Score 0–0.5:
        Checks that key entities/terms in the answer also appear in the
        retrieved context.  If the answer introduces many novel terms not
        present in any chunk, it may be hallucinating.

    Completeness  Score 0–0.3:
        Penalises very short answers (< 50 words) or answers that are
        obviously hedge statements ("I don't know").

    Format bonus  Score 0–0.2:
        Awards points for structured answers (headers, bullet points)
        indicating the model engaged meaningfully with the prompt.
    ─────────────────────────────────────────────────────────
    Total confidence = sum of above components, clipped to [0, 1].
    """

    def evaluate(
        self,
        answer:   str,
        question: str,
        results:  List[RetrievalResult],
    ) -> EvaluationResult:
        warnings: List[str] = []

        # ── 1. Groundedness ───────────────────────────────────
        ground_score, ground_warn = self._check_groundedness(answer, results)
        warnings.extend(ground_warn)

        # ── 2. Completeness ───────────────────────────────────
        complete_score, complete_warn = self._check_completeness(answer, question)
        warnings.extend(complete_warn)

        # ── 3. Format bonus ───────────────────────────────────
        format_score = self._check_format(answer)

        # ── Aggregate ─────────────────────────────────────────
        total      = min(1.0, ground_score + complete_score + format_score)
        is_grounded = ground_score >= 0.25
        is_complete = complete_score >= 0.15

        logger.info(
            f"EvaluationAgent: confidence={total:.2f} "
            f"(ground={ground_score:.2f}, complete={complete_score:.2f}, fmt={format_score:.2f})"
        )

        return EvaluationResult(
            confidence  = round(total, 3),
            is_grounded = is_grounded,
            is_complete = is_complete,
            warnings    = warnings,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _check_groundedness(
        self, answer: str, results: List[RetrievalResult]
    ) -> tuple[float, List[str]]:
        """
        Heuristic: extract noun tokens from the answer; check what fraction
        appear in the retrieved context.
        """
        warnings: List[str] = []
        if not results:
            warnings.append("No retrieved context — groundedness cannot be verified.")
            return 0.1, warnings

        # Build vocabulary of all context words (lowercased, 4+ chars)
        context_words: set[str] = set()
        for r in results:
            words = re.findall(r"\b[a-z]{4,}\b", r.chunk.text.lower())
            context_words.update(words)

        # Extract meaningful words from the answer
        answer_words = re.findall(r"\b[a-z]{4,}\b", answer.lower())
        if not answer_words:
            return 0.1, ["Answer contains no substantive words."]

        # Fraction of answer words that appear in context
        overlap = sum(1 for w in answer_words if w in context_words)
        ratio   = overlap / len(answer_words)

        if ratio < 0.3:
            warnings.append(
                f"Low groundedness ({ratio:.0%}): answer may contain information not in context."
            )

        # Scale to [0, 0.5]
        score = min(0.5, ratio * 0.6)
        return score, warnings

    def _check_completeness(
        self, answer: str, question: str
    ) -> tuple[float, List[str]]:
        """
        Penalise very short answers or hedge-only responses.
        """
        warnings: List[str] = []
        word_count = len(answer.split())

        hedge_phrases = [
            "i don't know", "cannot be found", "not available",
            "no information", "unable to answer",
        ]
        is_hedge = any(p in answer.lower() for p in hedge_phrases)

        if word_count < 30:
            warnings.append("Answer is very short — may be incomplete.")
            return 0.05, warnings

        if is_hedge and word_count < 80:
            warnings.append("Answer is primarily a hedge with little substance.")
            return 0.10, warnings

        # Reward longer, more complete answers up to 300 words
        score = min(0.3, 0.1 + (word_count / 300) * 0.2)
        return score, warnings

    def _check_format(self, answer: str) -> float:
        """
        Award up to 0.2 for structured formatting (headers, bullets, tables).
        """
        has_headers  = bool(re.search(r"#{1,3} ", answer) or re.search(r"\*\*[^*]+\*\*", answer))
        has_bullets  = bool(re.search(r"^[\-\*\•] ", answer, re.MULTILINE))
        has_table    = bool(re.search(r"\|.+\|", answer))
        has_numbered = bool(re.search(r"^\d+\.", answer, re.MULTILINE))

        bonus = sum([has_headers, has_bullets, has_table, has_numbered])
        return min(0.2, bonus * 0.05)
