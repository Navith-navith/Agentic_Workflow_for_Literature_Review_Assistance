"use client";

// app/page.tsx — Root page: wires Sidebar + ChatWindow + ChatInput

import { useState, useCallback, useEffect } from "react";
import { X } from "lucide-react";
//import { v4 as uuid } from "crypto";

import Sidebar    from "@/components/layout/Sidebar";
import ChatWindow from "@/components/chat/ChatWindow";
import ChatInput  from "@/components/chat/ChatInput";

import { ChatMessage, DocumentInfo, AgentResponse } from "@/types";
import {
  queryDocuments,
  summarizeDocuments,
  compareDocuments,
  listDocuments,
} from "@/lib/api";

// Simple UUID shim (crypto.randomUUID may not exist in all envs)
function newId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export default function HomePage() {
  const [documents,    setDocuments]    = useState<DocumentInfo[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [messages,     setMessages]     = useState<ChatMessage[]>([]);
  const [isLoading,    setIsLoading]    = useState(false);
  const [showResultsPanel, setShowResultsPanel] = useState(false);
  const [showScoreGraph, setShowScoreGraph] = useState(false);
  const [openSourceMessageId, setOpenSourceMessageId] = useState<string | null>(null);

  // ── Load existing indexed documents on mount ──────────────────────────────
  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch(() => {/* backend may not be up yet */});
  }, []);

  // ── Append a message ──────────────────────────────────────────────────────
  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages((prev) => [...prev, msg]);
    return msg;
  }, []);

  const replaceMessage = useCallback((id: string, updates: Partial<ChatMessage>) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, ...updates } : m))
    );
  }, []);

  // ── Detect intent from query text to choose the right API ────────────────
  const detectAction = (
    text: string,
    hint?: "query" | "summarize" | "compare"
  ): "query" | "summarize" | "compare" => {
    if (hint && hint !== "query") return hint;
    const t = text.toLowerCase();
    if (/\bcompar(e|ing|ison)\b/.test(t)) return "compare";
    if (/\bsummar(ize|ise|y)\b/.test(t))  return "summarize";
    return "query";
  };

  // ── Main send handler ─────────────────────────────────────────────────────
  const handleSend = useCallback(
    async (text: string, actionHint?: "query" | "summarize" | "compare") => {
      if (isLoading) return;

      // Add user message
      addMessage({
        id:        newId(),
        role:      "user",
        content:   text,
        timestamp: new Date(),
      });

      // Add placeholder assistant message (thinking state)
      const assistantId = newId();
      addMessage({
        id:        assistantId,
        role:      "assistant",
        content:   "",
        timestamp: new Date(),
        isLoading: true,
      });

      setIsLoading(true);

      try {
        const action  = detectAction(text, actionHint);
        const docScope = selectedDocs.length > 0 ? selectedDocs : undefined;

        let response: AgentResponse;

        if (action === "compare" && documents.length >= 2) {
          // Use selected docs for comparison, or all docs if none selected
          const docsToCompare = docScope ?? documents.map((d) => d.doc_id);
          response = await compareDocuments({ doc_ids: docsToCompare });
        } else if (action === "summarize") {
          const docsToSummarise = docScope ?? documents.map((d) => d.doc_id);
          response = await summarizeDocuments({ doc_ids: docsToSummarise, focus: text });
        } else {
          response = await queryDocuments({
            question: text,
            doc_ids:  docScope,
            top_k:    6,
          });
        }

        replaceMessage(assistantId, {
          content:    response.answer,
          intent:     response.intent,
          sources:    response.sources,
          confidence: response.confidence ?? undefined,
          isLoading:  false,
        });
        setOpenSourceMessageId(null);
        setShowResultsPanel(true);
      } catch (err: unknown) {
        const errMsg =
          err instanceof Error ? err.message : "An unexpected error occurred.";
        replaceMessage(assistantId, {
          content:   `⚠️ **Error:** ${errMsg}\n\nPlease ensure the backend is running and your GROQ_API_KEY is set.`,
          isLoading: false,
        });
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, documents, selectedDocs, addMessage, replaceMessage]
  );

  const latestAssistantResponse = [...messages]
    .reverse()
    .find((message) =>
      message.role === "assistant" && !message.isLoading && message.sources && message.sources.length > 0
    );

  return (
    <>
      <div className="flex h-screen w-screen overflow-hidden dot-grid">
      {/* Left: Document sidebar */}
      <Sidebar
        documents={documents}
        onDocumentsChange={setDocuments}
        selectedDocs={selectedDocs}
        onSelectDocs={setSelectedDocs}
      />

      {/* Right: Chat area */}
      <main className="flex flex-col flex-1 min-w-0 h-full overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-3 border-b border-[var(--border)] shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              Research Chat
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              {documents.length === 0
                ? "No documents indexed"
                : `${documents.length} paper${documents.length !== 1 ? "s" : ""} available`}
              {selectedDocs.length > 0 && ` · ${selectedDocs.length} selected`}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => {
                setMessages([]);
                setShowResultsPanel(false);
                setOpenSourceMessageId(null);
                setShowScoreGraph(false);
              }}
              className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--bg-card)] px-3 py-1 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:border-[var(--brand)] hover:text-[var(--brand)]"
            >
              <X className="w-3.5 h-3.5" />
              Clear chat
            </button>

            {['Reasoning', 'Retrieval', 'LLM', 'Eval'].map((label) => (
              <div key={label} className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
                <span
                  className={`w-1.5 h-1.5 rounded-full transition-colors duration-300
                    ${isLoading
                      ? "bg-[var(--brand)] animate-pulse"
                      : documents.length > 0
                      ? "bg-emerald-500"
                      : "bg-[var(--border)]"
                    }`}
                />
                {label}
              </div>
            ))}
          </div>
        </header>

        <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
          {/* Chat messages */}
          <ChatWindow
            messages={messages}
            documents={documents}
            showResultsPanel={showResultsPanel}
            openSourceMessageId={openSourceMessageId}
            onToggleResults={() => {
              setOpenSourceMessageId(null);
              setShowResultsPanel((prev) => !prev);
            }}
            onToggleSource={(messageId) => {
              if (messageId !== null) {
                setShowResultsPanel(false);
              }
              setOpenSourceMessageId(messageId);
            }}
            footer={showResultsPanel && latestAssistantResponse ? (
              <div className="mt-4 rounded-3xl border border-[var(--border)] bg-[var(--bg-card)] p-4 shadow-lg">
                <ResultsPanel
                  response={latestAssistantResponse}
                  showScoreGraph={showScoreGraph}
                  onToggleGraph={() => setShowScoreGraph((prev) => !prev)}
                />
              </div>
            ) : undefined}
          />
        </div>

        <div className="border-t border-[var(--border)] bg-[var(--bg-base)]">
          <ChatInput
            onSend={handleSend}
            isLoading={isLoading}
            documents={documents}
            selectedDocs={selectedDocs}
          />
        </div>
      </main>
    </div>
    </>
  );
}

function ResultsPanel({
  response,
  showScoreGraph,
  onToggleGraph,
}: {
  response: ChatMessage;
  showScoreGraph: boolean;
  onToggleGraph: () => void;
}) {
  const sources = response.sources ?? [];
  const confidenceValue = response.confidence ?? 0;
  const maxHybrid = Math.max(...sources.map((s) => s.hybrid_score), 0.01);

  return (
    <section className="px-6 py-4 border-t border-[var(--border)] bg-[var(--bg-subtle)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--text-muted)]">
            Results Panel
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-full border border-[var(--border)] bg-[var(--bg-card)] px-3 py-1 text-xs font-semibold text-[var(--text-primary)]">
              Intent: {response.intent ?? "unknown"}
            </span>
            <span className="inline-flex items-center rounded-full border border-[var(--border)] bg-[var(--bg-card)] px-3 py-1 text-xs text-[var(--text-secondary)]">
              {sources.length} source{sources.length !== 1 ? "s" : ""} retrieved
            </span>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:items-end">
          <label className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <input
              type="checkbox"
              checked={showScoreGraph}
              onChange={onToggleGraph}
              className="h-4 w-4 rounded border-[var(--border)] bg-[var(--bg-card)] text-[var(--brand)]"
            />
            Show Score Graph
          </label>
          <div className="min-w-[220px]">
            <div className="mb-1 text-xs uppercase tracking-[0.24em] text-[var(--text-muted)]">
              Confidence
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-[var(--border)]">
              <div
                className="h-full rounded-full bg-[var(--brand)] transition-all duration-300"
                style={{ width: `${Math.round(confidenceValue * 100)}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {Math.round(confidenceValue * 100)}% confidence
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 overflow-x-auto rounded-2xl border border-[var(--border)] bg-[var(--bg-card)]">
        <table className="min-w-full text-left text-xs text-[var(--text-secondary)]">
          <thead className="border-b border-[var(--border)] bg-[var(--bg-subtle)] text-[var(--text-muted)]">
            <tr>
              <th className="px-3 py-3">Rank</th>
              <th className="px-3 py-3">Document</th>
              <th className="px-3 py-3">Page</th>
              <th className="px-3 py-3">Semantic Score</th>
              <th className="px-3 py-3">Hybrid Score</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((source, index) => (
              <tr key={source.chunk.chunk_id} className="border-b border-[var(--border)] last:border-none">
                <td className="px-3 py-3 text-sm text-[var(--text-primary)]">{index + 1}</td>
                <td className="px-3 py-3 text-sm text-[var(--text-primary)]">{source.chunk.doc_id}</td>
                <td className="px-3 py-3 text-sm text-[var(--text-primary)]">
                  {source.chunk.page_number ?? "N/A"}
                </td>
                <td className="px-3 py-3 text-sm text-[var(--text-primary)]">{source.semantic_score.toFixed(3)}</td>
                <td className="px-3 py-3 text-sm text-[var(--text-primary)]">{source.hybrid_score.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showScoreGraph && (
        <div className="mt-6 rounded-3xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <div className="text-sm font-semibold text-[var(--text-primary)]">Hybrid Score Graph</div>
              <p className="text-xs text-[var(--text-muted)]">Visual ranking of the final hybrid retrieval score.</p>
            </div>
            <span className="rounded-full bg-[var(--bg-subtle)] px-3 py-1 text-xs uppercase tracking-[0.24em] text-[var(--text-muted)]">
              max {maxHybrid.toFixed(2)}
            </span>
          </div>

          <div className="space-y-3">
            {sources.map((source, index) => {
              const widthPercent = Math.round((source.hybrid_score / maxHybrid) * 100);
              const label = `${index + 1}. ${source.chunk.doc_id}`;
              const displayLabel = label.length > 30 ? `${label.slice(0, 27)}…` : label;

              return (
                <div key={source.chunk.chunk_id} className="rounded-2xl border border-[var(--border)] bg-[var(--bg-subtle)] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-[var(--text-primary)]">{displayLabel}</div>
                      <div className="text-xs text-[var(--text-muted)]">Page {source.chunk.page_number ?? 'N/A'}</div>
                    </div>
                    <span className="rounded-full bg-[var(--brand-dim)] px-2 py-1 text-[var(--text-primary)] text-xs font-semibold">
                      {source.hybrid_score.toFixed(3)}
                    </span>
                  </div>
                  <div className="mt-3 h-3 w-full overflow-hidden rounded-full bg-[var(--border)]">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-sky-400 to-cyan-400 transition-all duration-300"
                      style={{ width: `${widthPercent}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
