"use client";

// components/chat/MessageBubble.tsx
// Renders a single chat message — user or assistant

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Cpu, User, ChevronDown, ChevronUp, Shield, AlertTriangle } from "lucide-react";
import { ChatMessage, RetrievalResult } from "@/types";

const INTENT_LABELS: Record<string, { label: string; color: string }> = {
  qa:        { label: "Q&A",          color: "text-sky-400 bg-sky-400/10 border-sky-400/20" },
  summarize: { label: "Summary",      color: "text-violet-400 bg-violet-400/10 border-violet-400/20" },
  compare:   { label: "Comparison",   color: "text-amber-400 bg-amber-400/10 border-amber-400/20" },
  trend:     { label: "Trend Analysis", color: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20" },
  general:   { label: "General",      color: "text-slate-400 bg-slate-400/10 border-slate-400/20" },
};

interface Props {
  message: ChatMessage;
  onToggleResults?: () => void;
  showResultsPanel?: boolean;
  showSources?: boolean;
  onToggleSources?: (messageId: string | null) => void;
}

export default function MessageBubble({
  message,
  onToggleResults,
  showResultsPanel,
  showSources = false,
  onToggleSources,
}: Props) {
  const isUser      = message.role === "user";
  const intentMeta  = message.intent ? INTENT_LABELS[message.intent] : null;

  if (message.isLoading) {
    return <ThinkingBubble />;
  }

  return (
    <div
      className={`flex gap-3 w-full animate-slide-up
        ${isUser ? "flex-row-reverse" : "flex-row"}
      `}
    >
      {/* Avatar */}
      <div
        className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center border
          ${isUser
            ? "bg-[var(--brand-dim)] border-[var(--brand-dim)] text-white"
            : "bg-[var(--bg-card)] border-[var(--border)] text-[var(--brand)]"
          }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Cpu className="w-4 h-4" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[80%] flex flex-col gap-2 ${isUser ? "items-end" : "items-start"}`}>

        {/* Intent badge */}
        {!isUser && intentMeta && (
          <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border
              tracking-wide uppercase ${intentMeta.color}`}
          >
            {intentMeta.label}
          </span>
        )}

        {/* Content */}
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed
            ${isUser
              ? "bg-[var(--brand-dim)] text-white rounded-tr-sm"
              : "bg-[var(--bg-card)] border border-[var(--border)] text-[var(--text-primary)] rounded-tl-sm"
            }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose-dark max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Footer: confidence + sources */}
        {!isUser && (
          <div className="flex items-center gap-3 px-1">
            {/* Confidence score */}
            {message.confidence !== undefined && message.confidence !== null && (
              <ConfidenceBar value={message.confidence} />
            )}

            {/* Sources toggle */}
            {message.sources && message.sources.length > 0 && (
              <>
                <button
                  onClick={() => {
                    const willOpen = !showSources;
                    if (willOpen && showResultsPanel && onToggleResults) {
                      onToggleResults();
                    }
                    onToggleSources?.(willOpen ? message.id : null);
                  }}
                  className="flex items-center gap-1 text-xs text-[var(--text-muted)]
                    hover:text-[var(--brand)] transition-colors"
                >
                  {showSources
                    ? <><ChevronUp className="w-3 h-3" /> Hide sources</>
                    : <><ChevronDown className="w-3 h-3" /> {message.sources.length} sources</>
                  }
                </button>
                {onToggleResults && (
                  <button
                    onClick={() => {
                      if (!showResultsPanel && onToggleSources) {
                        onToggleSources(null);
                      }
                      onToggleResults();
                    }}
                    className="flex items-center gap-1 text-xs text-[var(--text-muted)]
                      hover:text-[var(--brand)] transition-colors"
                  >
                    {showResultsPanel
                      ? <><ChevronUp className="w-3 h-3" /> Hide results</>
                      : <><ChevronDown className="w-3 h-3" /> Show results</>
                    }
                  </button>
                )}
              </>
            )}

            {/* Timestamp */}
            <span className="text-xs text-[var(--text-muted)] ml-auto">
              {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        )}

        {/* Sources panel */}
        {!isUser && showSources && message.sources && (
          <SourcesPanel sources={message.sources} />
        )}
      </div>
    </div>
  );
}

/* ── Sub-components ─────────────────────────────────────────────────────── */

function ThinkingBubble() {
  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="w-8 h-8 rounded-full flex items-center justify-center border
        bg-[var(--bg-card)] border-[var(--border)] text-[var(--brand)] shrink-0"
      >
        <Cpu className="w-4 h-4" />
      </div>
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl rounded-tl-sm
        px-5 py-4 flex items-center gap-2.5"
      >
        <ThinkingDot delay="0ms"   />
        <ThinkingDot delay="200ms" />
        <ThinkingDot delay="400ms" />
        <span className="text-xs text-[var(--text-muted)] ml-1">Agents thinking…</span>
      </div>
    </div>
  );
}

function ThinkingDot({ delay }: { delay: string }) {
  return (
    <span
      className="w-2 h-2 rounded-full bg-[var(--brand)] opacity-40"
      style={{
        animation: `breathe 1.2s ease-in-out ${delay} infinite`,
      }}
    />
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct   = Math.round(value * 100);
  const color = pct >= 70 ? "text-emerald-400" : pct >= 45 ? "text-amber-400" : "text-red-400";
  const Icon  = pct >= 50 ? Shield : AlertTriangle;

  return (
    <div className={`flex items-center gap-1 text-xs ${color}`}>
      <Icon className="w-3 h-3" />
      <span>{pct}% confidence</span>
    </div>
  );
}

function SourcesPanel({ sources }: { sources: RetrievalResult[] }) {
  return (
    <div className="w-full space-y-1.5 animate-fade-in">
      <p className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider px-1">
        Retrieved Sources
      </p>
      {sources.slice(0, 4).map((r, i) => (
        <div
          key={r.chunk.chunk_id + i}
          className="bg-[var(--bg-card)] border border-[var(--border-subtle)]
            rounded-xl p-3 text-xs space-y-1.5"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium text-[var(--brand)] truncate max-w-[200px]" title={r.chunk.doc_id}>
              {r.chunk.doc_id}
            </span>
            <div className="flex gap-2 shrink-0">
              {r.chunk.page_number && (
                <span className="text-[var(--text-muted)]">p.{r.chunk.page_number}</span>
              )}
              <ScorePill label="hybrid" value={r.hybrid_score} />
            </div>
          </div>
          <p className="text-[var(--text-secondary)] leading-relaxed line-clamp-3">
            {r.chunk.text}
          </p>
          <div className="flex gap-3 text-[var(--text-muted)]">
            <span>sem: {(r.semantic_score * 100).toFixed(0)}%</span>
            <span>bm25: {(r.bm25_score * 100).toFixed(0)}%</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ScorePill({ label, value }: { label: string; value: number }) {
  const pct   = Math.round(value * 100);
  const color = pct >= 60 ? "bg-emerald-500/15 text-emerald-400"
              : pct >= 35 ? "bg-amber-500/15 text-amber-400"
              :              "bg-slate-500/15 text-slate-400";
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${color}`}>
      {label} {pct}%
    </span>
  );
}
