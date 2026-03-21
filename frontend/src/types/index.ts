// types/index.ts — Shared TypeScript types matching backend Pydantic models

export type QueryIntent = "qa" | "summarize" | "compare" | "trend" | "general";

export interface DocumentChunk {
  chunk_id:    string;
  doc_id:      string;
  text:        string;
  page_number: number | null;
  metadata:    Record<string, unknown>;
}

export interface RetrievalResult {
  chunk:          DocumentChunk;
  semantic_score: number;
  bm25_score:     number;
  hybrid_score:   number;
}

export interface AgentResponse {
  answer:       string;
  intent:       QueryIntent;
  sources:      RetrievalResult[];
  doc_ids_used: string[];
  confidence:   number | null;
  reasoning:    string | null;
  metadata:     Record<string, unknown>;
}

export interface DocumentInfo {
  doc_id:     string;
  filename:   string;
  num_pages:  number;
  num_chunks: number;
}

export interface UploadResponse {
  doc_id:     string;
  filename:   string;
  num_chunks: number;
  status:     string;
}

// ── Chat message types ────────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id:        string;
  role:      MessageRole;
  content:   string;
  timestamp: Date;
  intent?:   QueryIntent;
  sources?:  RetrievalResult[];
  confidence?: number;
  isLoading?: boolean;
}
