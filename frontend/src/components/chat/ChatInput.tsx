"use client";

// components/chat/ChatInput.tsx
// Input bar with quick-action buttons for summarize / compare

import { useState, useRef, KeyboardEvent } from "react";
import {
  Send, FileSearch, GitCompare, TrendingUp, RotateCcw,
} from "lucide-react";
import { DocumentInfo } from "@/types";

interface ChatInputProps {
  onSend:     (text: string, action?: "query" | "summarize" | "compare") => void;
  isLoading:  boolean;
  documents:  DocumentInfo[];
  selectedDocs: string[];
}

const QUICK_PROMPTS = [
  { label: "Summarize paper",    icon: FileSearch,  text: "Summarize this paper" },
  { label: "Compare papers",     icon: GitCompare,  text: "Compare the selected papers" },
  { label: "What are the trends?", icon: TrendingUp, text: "What are the main trends in these papers?" },
];

export default function ChatInput({
  onSend,
  isLoading,
  documents,
  selectedDocs,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const hasDocuments = documents.length > 0;

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed, "query");
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    // Auto-grow textarea
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  return (
    <div className="border-t border-[var(--border)] bg-[var(--bg-base)] px-4 pt-3 pb-4 space-y-2.5">

      {/* ── Quick action buttons ───────────────────────────────── */}
      {hasDocuments && (
        <div className="flex gap-2 flex-wrap">
          {QUICK_PROMPTS.map(({ label, icon: Icon, text }) => (
            <button
              key={label}
              disabled={isLoading}
              onClick={() => {
                onSend(text, "query");
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs
                border border-[var(--border)] text-[var(--text-muted)]
                hover:text-[var(--brand)] hover:border-[var(--brand-dim)]
                hover:bg-[var(--brand-glow)] transition-all duration-150
                disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Icon className="w-3 h-3" />
              {label}
            </button>
          ))}

          {selectedDocs.length >= 2 && (
            <button
              disabled={isLoading}
              onClick={() =>
                onSend(
                  `Compare these papers: ${selectedDocs.join(", ")}`,
                  "compare"
                )
              }
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs
                border border-amber-500/30 text-amber-400
                hover:bg-amber-400/10 transition-all duration-150
                disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <GitCompare className="w-3 h-3" />
              Compare {selectedDocs.length} selected
            </button>
          )}
        </div>
      )}

      {/* ── Textarea + send ────────────────────────────────────── */}
      <div
        className={`flex items-end gap-2 rounded-2xl border px-4 py-3 transition-all duration-200
          ${isLoading
            ? "border-[var(--border)] opacity-80"
            : "border-[var(--border)] focus-within:border-[var(--brand-dim)] focus-within:bg-[var(--bg-card)]"
          }
          bg-[var(--bg-card)]
        `}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleTextareaChange}
          onKeyDown={handleKeyDown}
          disabled={isLoading || !hasDocuments}
          rows={1}
          placeholder={
            !hasDocuments
              ? "Upload a research paper to start querying…"
              : selectedDocs.length > 0
              ? `Ask about ${selectedDocs.length} selected paper(s)…`
              : "Ask anything about the research papers… (Shift+Enter for newline)"
          }
          className="flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)]
            resize-none focus:outline-none leading-relaxed min-h-[24px] max-h-[160px]"
          style={{ height: "24px" }}
        />

        <button
          onClick={submit}
          disabled={!value.trim() || isLoading || !hasDocuments}
          className={`shrink-0 p-2 rounded-xl transition-all duration-200
            ${value.trim() && !isLoading && hasDocuments
              ? "bg-[var(--brand-dim)] text-white hover:brightness-110 brand-glow"
              : "bg-[var(--border)] text-[var(--text-muted)] cursor-not-allowed"
            }`}
        >
          {isLoading
            ? <RotateCcw className="w-4 h-4 animate-spin" />
            : <Send className="w-4 h-4" />
          }
        </button>
      </div>

      {/* ── Scope hint ─────────────────────────────────────────── */}
      {selectedDocs.length > 0 && (
        <p className="text-xs text-[var(--text-muted)] px-1">
          🔍 Searching within:{" "}
          <span className="text-[var(--brand)]">
            {selectedDocs.slice(0, 2).join(", ")}
            {selectedDocs.length > 2 ? ` +${selectedDocs.length - 2} more` : ""}
          </span>
        </p>
      )}
    </div>
  );
}
