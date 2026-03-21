// lib/api.ts — Typed API client for the FastAPI backend.
// All fetch calls go through here; components never call fetch() directly.

import {
  AgentResponse,
  DocumentInfo,
  UploadResponse,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ── Document endpoints ────────────────────────────────────────────────────────

export async function uploadPDF(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${BASE_URL}/upload`, {
    method: "POST",
    body:   form,
    // Don't set Content-Type — browser sets multipart boundary automatically
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  return request<DocumentInfo[]>("/documents");
}

export async function deleteDocument(docId: string): Promise<void> {
  await request(`/documents/${encodeURIComponent(docId)}`, { method: "DELETE" });
}

// ── Query endpoints ───────────────────────────────────────────────────────────

export interface QueryParams {
  question: string;
  doc_ids?:  string[];
  top_k?:    number;
}

export async function queryDocuments(params: QueryParams): Promise<AgentResponse> {
  return request<AgentResponse>("/query", {
    method: "POST",
    body:   JSON.stringify({ top_k: 5, ...params }),
  });
}

export interface SummarizeParams {
  doc_ids: string[];
  focus?:  string;
}

export async function summarizeDocuments(params: SummarizeParams): Promise<AgentResponse> {
  return request<AgentResponse>("/summarize", {
    method: "POST",
    body:   JSON.stringify(params),
  });
}

export interface CompareParams {
  doc_ids:  string[];
  aspects?: string[];
}

export async function compareDocuments(params: CompareParams): Promise<AgentResponse> {
  return request<AgentResponse>("/compare", {
    method: "POST",
    body:   JSON.stringify(params),
  });
}

export async function healthCheck(): Promise<{ status: string; model: string }> {
  return request("/health");
}
