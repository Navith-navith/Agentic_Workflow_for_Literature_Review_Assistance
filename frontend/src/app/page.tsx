"use client";

// app/page.tsx — Root page: wires Sidebar + ChatWindow + ChatInput

import { useState, useCallback, useEffect } from "react";
import { v4 as uuid } from "crypto";

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

  return (
    <div className="flex h-screen w-screen overflow-hidden dot-grid">
      {/* Left: Document sidebar */}
      <Sidebar
        documents={documents}
        onDocumentsChange={setDocuments}
        selectedDocs={selectedDocs}
        onSelectDocs={setSelectedDocs}
      />

      {/* Right: Chat area */}
      <main className="flex flex-col flex-1 min-w-0 h-full">
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

          {/* Agent status indicators */}
          <div className="flex items-center gap-2">
            {["Reasoning", "Retrieval", "LLM", "Eval"].map((label) => (
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

        {/* Chat messages */}
        <ChatWindow messages={messages} documents={documents} />

        {/* Input bar */}
        <ChatInput
          onSend={handleSend}
          isLoading={isLoading}
          documents={documents}
          selectedDocs={selectedDocs}
        />
      </main>
    </div>
  );
}
