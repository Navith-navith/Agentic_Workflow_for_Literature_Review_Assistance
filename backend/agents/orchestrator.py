"""
orchestrator.py — Coordinates all agents for each API request.

The Orchestrator is the only place that knows the full agent graph.
All API routes call the Orchestrator — never individual agents directly.

Pipeline:
  Upload:  DocumentAgent.process_pdf()
  Query:   ReasoningAgent → RetrievalAgent → AnswerGenerationAgent → EvaluationAgent
  Summary: ReasoningAgent (override) → DocumentAgent.get_chunks → AnswerGeneration
  Compare: ReasoningAgent (override) → RetrievalAgent (multi-doc) → AnswerGeneration
"""
from __future__ import annotations

from typing import List, Optional
from loguru import logger

from core.models import (
    AgentResponse, QueryIntent, QueryRequest,
    SummarizeRequest, CompareRequest, UploadResponse, DocumentInfo, RetrievalResult,
)
from agents.reasoning_agent   import ReasoningAgent
from agents.retrieval_agent   import RetrievalAgent
from agents.document_agent    import DocumentAgent
from agents.answer_generation_agent import AnswerGenerationAgent
from agents.evaluation_agent  import EvaluationAgent
from core.config import settings


class AgentOrchestrator:
    """
    Singleton that owns all agent instances and routes requests.

    Agents are initialised once at startup (expensive operations like
    loading embedding models happen here, not per-request).
    """

    def __init__(self):
        logger.info("Orchestrator: initialising agents…")
        self.retrieval_agent  = RetrievalAgent()
        self.document_agent   = DocumentAgent(self.retrieval_agent)
        self.answer_agent     = AnswerGenerationAgent()
        self.evaluation_agent = EvaluationAgent()
        logger.info("Orchestrator: all agents ready")

    # ── Document ingestion ────────────────────────────────────────────────────

    def ingest_pdf(self, file_path: str, original_filename: str) -> UploadResponse:
        """Process a newly uploaded PDF end-to-end."""
        info = self.document_agent.process_pdf(file_path, original_filename)
        return UploadResponse(
            doc_id     = info.doc_id,
            filename   = info.filename,
            num_chunks = info.num_chunks,
        )

    def list_documents(self) -> List[DocumentInfo]:
        return self.document_agent.list_documents()

    def delete_document(self, doc_id: str) -> bool:
        return self.document_agent.delete_document(doc_id)

    # ── Query pipeline ────────────────────────────────────────────────────────

    def query(self, req: QueryRequest) -> AgentResponse:
        """General question-answering pipeline."""
        logger.info(f"Orchestrator.query: '{req.question[:80]}'")

        # 1. Reasoning — understand intent
        reasoning_agent = ReasoningAgent(
            available_doc_ids=self.document_agent.available_doc_ids()
        )
        plan = reasoning_agent.plan(req.question)

        # 2. Retrieval — hybrid search
        doc_filter = req.doc_ids or (plan.target_doc_ids or None)
        results = self.retrieval_agent.retrieve(
            query   = plan.refined_query,
            top_k   = req.top_k,
            doc_ids = doc_filter,
        )

        # 3. Answer generation
        answer = self.answer_agent.generate(plan, results, req.question)

        # 4. Evaluation
        eval_result = self.evaluation_agent.evaluate(answer, req.question, results)

        return AgentResponse(
            answer       = answer,
            intent       = plan.intent,
            sources      = results,
            doc_ids_used = list({r.chunk.doc_id for r in results}),
            confidence   = eval_result.confidence,
            reasoning    = plan.reasoning_trace,
            metadata     = {
                "warnings":       eval_result.warnings,
                "is_grounded":    eval_result.is_grounded,
                "is_complete":    eval_result.is_complete,
                "refined_query":  plan.refined_query,
            },
        )

    # ── Summarise pipeline ────────────────────────────────────────────────────

    def summarize(self, req: SummarizeRequest) -> AgentResponse:
        """Summarise one or more documents."""
        logger.info(f"Orchestrator.summarize: docs={req.doc_ids}")

        question = req.focus or f"Summarize the following papers: {', '.join(req.doc_ids)}"

        # Pull all chunks for the requested docs from the vector store
        all_chunks = []
        for doc_id in req.doc_ids:
            chunks = self.document_agent.get_chunks_for_doc(doc_id)
            all_chunks.extend(chunks)

        if not all_chunks:
            # Fall back to retrieval if direct chunk lookup fails
            results = self.retrieval_agent.retrieve(
                query   = question,
                top_k   = 10,
                doc_ids = req.doc_ids,
            )
        else:
            # Wrap raw chunks in RetrievalResult for uniform downstream API
            results = [
                RetrievalResult(chunk=c, semantic_score=1.0, bm25_score=1.0, hybrid_score=1.0)
                for c in all_chunks[:20]     # Cap at 20 chunks to stay within context
            ]

        from agents.reasoning_agent import ReasoningPlan
        plan = ReasoningPlan(
            intent        = QueryIntent.SUMMARIZE,
            refined_query = question,
            target_doc_ids= req.doc_ids,
        )

        answer = self.answer_agent.generate(plan, results, question)
        eval_r = self.evaluation_agent.evaluate(answer, question, results)

        return AgentResponse(
            answer       = answer,
            intent       = QueryIntent.SUMMARIZE,
            sources      = results[:5],     # Return representative sources
            doc_ids_used = req.doc_ids,
            confidence   = eval_r.confidence,
            metadata     = {"warnings": eval_r.warnings},
        )

    # ── Compare pipeline ──────────────────────────────────────────────────────

    def compare(self, req: CompareRequest) -> AgentResponse:
        """Compare two or more documents."""
        logger.info(f"Orchestrator.compare: docs={req.doc_ids}")

        aspect_str = ", ".join(req.aspects) if req.aspects else "methodology, results, contributions"
        question   = f"Compare these papers on {aspect_str}: {', '.join(req.doc_ids)}"

        # Retrieve representative chunks from each paper
        all_results: List[RetrievalResult] = []
        for doc_id in req.doc_ids:
            res = self.retrieval_agent.retrieve(
                query   = aspect_str,
                top_k   = 4,
                doc_ids = [doc_id],
            )
            all_results.extend(res)

        from agents.reasoning_agent import ReasoningPlan
        plan = ReasoningPlan(
            intent         = QueryIntent.COMPARE,
            refined_query  = question,
            target_doc_ids = req.doc_ids,
            aspects        = req.aspects or [],
        )

        answer = self.answer_agent.generate(plan, all_results, question)
        eval_r = self.evaluation_agent.evaluate(answer, question, all_results)

        return AgentResponse(
            answer       = answer,
            intent       = QueryIntent.COMPARE,
            sources      = all_results[:6],
            doc_ids_used = req.doc_ids,
            confidence   = eval_r.confidence,
            metadata     = {"warnings": eval_r.warnings, "aspects": req.aspects},
        )
