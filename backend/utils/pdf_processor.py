"""
pdf_processor.py — Extracts and cleans text from PDF files.

Strategy:
  1. Try pdfplumber first (best for scanned/complex layouts).
  2. Fall back to PyPDF2 for simple text PDFs.
  3. Return a list of (page_number, cleaned_text) tuples.
"""
import re
from pathlib import Path
from typing import List, Tuple

import pdfplumber
import PyPDF2
from loguru import logger


def _clean_text(raw: str) -> str:
    """
    Remove noise from extracted PDF text:
    - Collapse excessive whitespace / newlines
    - Drop lines that are purely numeric (page numbers, table indices)
    - Strip ligature artefacts common in academic PDFs
    """
    # Replace ligature characters with ASCII equivalents
    ligatures = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}
    for lig, rep in ligatures.items():
        raw = raw.replace(lig, rep)

    # Collapse multiple spaces to one
    text = re.sub(r" {2,}", " ", raw)

    # Remove lines that are only digits (page numbers, table row numbers)
    lines = [ln for ln in text.splitlines() if not re.fullmatch(r"\s*\d+\s*", ln)]

    # Collapse excessive blank lines
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_pages(pdf_path: str) -> List[Tuple[int, str]]:
    """
    Extract text page-by-page from a PDF.

    Returns:
        List of (page_number, page_text) tuples (1-indexed pages).
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages: List[Tuple[int, str]] = []

    # ── Primary: pdfplumber ───────────────────────────────────
    try:
        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                raw = page.extract_text() or ""
                if raw.strip():
                    pages.append((i, _clean_text(raw)))
        if pages:
            logger.info(f"pdfplumber extracted {len(pages)} pages from {path.name}")
            return pages
    except Exception as e:
        logger.warning(f"pdfplumber failed ({e}), falling back to PyPDF2")

    # ── Fallback: PyPDF2 ──────────────────────────────────────
    with open(str(path), "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for i, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            if raw.strip():
                pages.append((i, _clean_text(raw)))

    logger.info(f"PyPDF2 extracted {len(pages)} pages from {path.name}")
    return pages


def chunk_pages(
    pages: List[Tuple[int, str]],
    chunk_size: int = 512,
    overlap: int = 64,
) -> List[Tuple[int, str]]:
    """
    Slide a fixed-size window over the concatenated page text to produce
    overlapping chunks.  Each chunk remembers its source page number.

    Args:
        pages:      List of (page_number, text) from extract_pages().
        chunk_size: Target character length per chunk.
        overlap:    Characters of overlap between consecutive chunks.

    Returns:
        List of (page_number, chunk_text) tuples.
    """
    chunks: List[Tuple[int, str]] = []

    for page_num, text in pages:
        start = 0
        while start < len(text):
            end   = start + chunk_size
            chunk = text[start:end].strip()
            if len(chunk) > 30:              # Skip tiny fragments
                chunks.append((page_num, chunk))
            start += chunk_size - overlap    # Slide with overlap

    return chunks
