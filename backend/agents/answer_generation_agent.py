"""
answer_generation_agent.py — Generates grounded answers via Groq (LLaMA 3).

Responsibilities:
  1. Build a structured prompt appropriate to the query intent
  2. Call the Groq API with the retrieved context chunks
  3. Stream or return the answer
  4. Handle rate limiting and retries gracefully

Prompt strategy differs by intent:
  QA        → RAG prompt: "Answer the question based only on the context."
  SUMMARIZE → Summarisation prompt per document, then synthesis
  COMPARE   → Structured comparison table prompt
  TREND     → Theme extraction prompt across all chunks
  GENERAL   → Open-ended synthesis prompt
"""
from __future__ import annotations

from typing import List, Optional

from groq import Groq
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from core.models import QueryIntent, RetrievalResult, DocumentChunk
from agents.reasoning_agent import ReasoningPlan


# Maximum context tokens we send to the LLM (safety cap for context window)
_MAX_CONTEXT_CHARS = 6000


class AnswerGenerationAgent:
    """
    Calls the Groq LLM to synthesise an answer from retrieved context.

    Each public method corresponds to a query intent, giving clear
    separation of prompting concerns.
    """

    def __init__(self):
        self._client = Groq(api_key=settings.groq_api_key)
        self._model  = settings.llm_model
        logger.info(f"AnswerGenerationAgent: using model={self._model}")

    # ── Public dispatcher ─────────────────────────────────────────────────────

    def generate(
        self,
        plan:     ReasoningPlan,
        results:  List[RetrievalResult],
        question: str,
    ) -> str:
        """
        Route to the correct generation method based on intent.
        """
        if plan.intent == QueryIntent.SUMMARIZE:
            return self.summarize(results, question)
        elif plan.intent == QueryIntent.COMPARE:
            return self.compare(results, question, plan.aspects)
        elif plan.intent == QueryIntent.TREND:
            return self.extract_trends(results, question, plan.focus_topic)
        else:
            # QA and GENERAL use the standard RAG answer
            return self.answer_question(results, question)

    # ── Intent-specific methods ───────────────────────────────────────────────

    def answer_question(self, results: List[RetrievalResult], question: str) -> str:
        """Standard RAG QA: ground the answer strictly in retrieved context."""
        context = self._build_context(results)
        prompt  = f"""You are an expert AI assistant specialising in healthcare engineering research.
Answer the following question based ONLY on the provided research paper excerpts.
If the answer cannot be found in the excerpts, say so clearly — do not hallucinate.

RESEARCH EXCERPTS:
{context}

QUESTION: {question}

Provide a precise, well-structured answer. Cite which paper each piece of information comes from.
"""
        return self._call_llm(prompt)

    def summarize(self, results: List[RetrievalResult], instruction: str) -> str:
        """Summarise the content found in retrieved chunks."""
        context = self._build_context(results)
        prompt  = f"""You are an expert research assistant specialising in healthcare engineering.
Produce a comprehensive yet concise summary of the following research paper excerpts.

Structure your summary as:
1. **Overview** – Core topic and research question
2. **Methodology** – Methods and approach used
3. **Key Findings** – Most important results and contributions
4. **Limitations** – Noted limitations or future work
5. **Clinical / Engineering Relevance** – Why this matters for healthcare

PAPER EXCERPTS:
{context}

USER REQUEST: {instruction}
"""
        return self._call_llm(prompt)

    def compare(
        self,
        results:  List[RetrievalResult],
        question: str,
        aspects:  Optional[List[str]] = None,
    ) -> str:
        """Compare papers across specified aspects."""
        context = self._build_context(results)
        aspect_list = ", ".join(aspects) if aspects else "methodology, findings, limitations, contributions"
        prompt  = f"""You are an expert research analyst specialising in healthcare engineering.
Compare the following research papers based on these aspects: {aspect_list}.

Structure your comparison as:
1. **Brief introduction** of each paper
2. **Comparison table** (use Markdown table format)
3. **Detailed analysis** of key differences and similarities
4. **Recommendation** — which approach is more suitable and for what context

PAPER EXCERPTS:
{context}

USER REQUEST: {question}
"""
        return self._call_llm(prompt)

    def extract_trends(
        self,
        results:     List[RetrievalResult],
        question:    str,
        focus_topic: Optional[str] = None,
    ) -> str:
        """Identify trends and patterns across multiple papers."""
        context = self._build_context(results)
        topic_hint = f" with a focus on '{focus_topic}'" if focus_topic else ""
        prompt  = f"""You are an expert research analyst specialising in healthcare engineering.
Analyse the following research paper excerpts{topic_hint} and identify:

1. **Major trends** – recurring themes and directions
2. **Methodological patterns** – common or evolving approaches
3. **Key open problems** – gaps still being addressed
4. **Emerging technologies** – new tools, algorithms, or frameworks
5. **Future directions** – where the field is heading

PAPER EXCERPTS:
{context}

USER REQUEST: {question}
"""
        return self._call_llm(prompt)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_context(self, results: List[RetrievalResult]) -> str:
        """
        Concatenate retrieved chunks into a labelled context string.
        Truncates at _MAX_CONTEXT_CHARS to stay within token limits.
        """
        parts = []
        total = 0
        for r in results:
            label  = f"[{r.chunk.doc_id} | Page {r.chunk.page_number}]"
            block  = f"{label}\n{r.chunk.text}"
            if total + len(block) > _MAX_CONTEXT_CHARS:
                remaining = _MAX_CONTEXT_CHARS - total
                if remaining > 100:
                    parts.append(block[:remaining] + "...")
                break
            parts.append(block)
            total += len(block)

        return "\n\n---\n\n".join(parts) if parts else "No relevant context found."

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _call_llm(self, prompt: str) -> str:
        """
        Call the Groq API.  Retries up to 3 times on transient errors.
        """
        try:
            response = self._client.chat.completions.create(
                model    = self._model,
                messages = [{"role": "user", "content": prompt}],
                temperature = 0.2,      # Low temperature for factual accuracy
                max_tokens  = 1500,
            )
            answer = response.choices[0].message.content
            logger.info(f"AnswerGenerationAgent: generated {len(answer)} chars")
            return answer
        except Exception as e:
            logger.error(f"AnswerGenerationAgent: LLM call failed — {e}")
            raise
