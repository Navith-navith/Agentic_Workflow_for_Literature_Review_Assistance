"""
main.py — FastAPI application entry point.

Routes:
  POST /upload        → Upload and index a PDF
  POST /query         → Ask a question (hybrid RAG)
  POST /summarize     → Summarise one or more papers
  POST /compare       → Compare papers
  GET  /documents     → List indexed documents
  DELETE /documents/{doc_id} → Remove a document
  GET  /health        → Health check
"""
import os
import shutil
from pathlib import Path
from typing import List

import aiofiles
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from core.config import settings
from core.models import (
    QueryRequest, SummarizeRequest, CompareRequest,
    AgentResponse, UploadResponse, DocumentInfo,
)
from agents.orchestrator import AgentOrchestrator


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "Healthcare RAG API",
    description = "Agent-Based Hybrid RAG for Healthcare Engineering Research Papers",
    version     = "1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.cors_origins,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Dependency: Orchestrator singleton ────────────────────────────────────────
# Created once at startup and injected into every route handler.

_orchestrator: AgentOrchestrator | None = None


@app.on_event("startup")
async def startup():
    global _orchestrator
    logger.info("Starting Healthcare RAG API…")
    _orchestrator = AgentOrchestrator()
    logger.info("API ready ✓")


def get_orchestrator() -> AgentOrchestrator:
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="System initialising, try again shortly")
    return _orchestrator


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Quick liveness check."""
    return {"status": "ok", "model": settings.llm_model}


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file:         UploadFile = File(...),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
):
    """
    Upload a PDF research paper and index it for retrieval.

    - Validates file type (PDF only)
    - Saves to disk under UPLOAD_DIR
    - Delegates full ingestion pipeline to the Orchestrator
    """
    # Validate file extension
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Save uploaded file
    dest = Path(settings.upload_dir) / file.filename
    async with aiofiles.open(str(dest), "wb") as out:
        content = await file.read()
        await out.write(content)

    logger.info(f"Saved upload: {dest} ({len(content):,} bytes)")

    try:
        response = orchestrator.ingest_pdf(str(dest), file.filename)
    except ValueError as e:
        # Clean up the saved file if ingestion fails
        os.remove(str(dest))
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        os.remove(str(dest))
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process PDF.")

    return response


@app.post("/query", response_model=AgentResponse)
async def query(
    req:          QueryRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
):
    """
    Ask a question over the indexed research papers.

    Supports:
    - Factual QA ("What is the accuracy of model X?")
    - Trend queries ("What are trends in drug delivery?")
    - General synthesis queries
    """
    try:
        return orchestrator.query(req)
    except Exception as e:
        logger.error(f"/query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/summarize", response_model=AgentResponse)
async def summarize(
    req:          SummarizeRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
):
    """
    Summarise one or more research papers.

    Optionally provide a focus area (e.g. "methodology" or "clinical impact").
    """
    # Validate doc_ids exist
    available = orchestrator.list_documents()
    available_ids = {d.doc_id for d in available}
    missing = [d for d in req.doc_ids if d not in available_ids]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Documents not found: {missing}. Available: {list(available_ids)}",
        )
    try:
        return orchestrator.summarize(req)
    except Exception as e:
        logger.error(f"/summarize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare", response_model=AgentResponse)
async def compare(
    req:          CompareRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
):
    """
    Compare two or more research papers across specified aspects.

    Example aspects: ["methodology", "results", "dataset", "limitations"]
    """
    available     = orchestrator.list_documents()
    available_ids = {d.doc_id for d in available}
    missing       = [d for d in req.doc_ids if d not in available_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Documents not found: {missing}")
    try:
        return orchestrator.compare(req)
    except Exception as e:
        logger.error(f"/compare error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents", response_model=List[DocumentInfo])
async def list_documents(
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
):
    """List all indexed research papers."""
    return orchestrator.list_documents()


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id:       str,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
):
    """Remove a document from the index and delete its file."""
    success = orchestrator.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    # Remove physical file
    file_path = Path(settings.upload_dir) / doc_id
    if file_path.exists():
        file_path.unlink()

    return {"status": "deleted", "doc_id": doc_id}


# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
