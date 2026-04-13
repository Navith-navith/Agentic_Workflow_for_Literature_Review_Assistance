"use client";

// components/chat/ChatWindow.tsx
// Scrollable message list with welcome screen

import { ReactNode, useEffect, useRef } from "react";
import { Brain, Zap, FileSearch, GitCompare } from "lucide-react";
import { ChatMessage, DocumentInfo } from "@/types";
import MessageBubble from "./MessageBubble";

interface ChatWindowProps {
  messages:            ChatMessage[];
  documents:           DocumentInfo[];
  footer?:             ReactNode;
  onToggleResults?:    () => void;
  showResultsPanel?:   boolean;
  openSourceMessageId?: string | null;
  onToggleSource?:     (messageId: string | null) => void;
}

export default function ChatWindow({ messages, documents, footer, onToggleResults, showResultsPanel, openSourceMessageId, onToggleSource }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const isEmpty = messages.length === 0;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5 pb-32">
      {isEmpty ? (
        <WelcomeScreen hasDocuments={documents.length > 0} />
      ) : (
        <>
          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onToggleResults={onToggleResults}
              showResultsPanel={showResultsPanel}
              showSources={msg.id === openSourceMessageId}
              onToggleSources={onToggleSource}
            />
          ))}
          {footer}
          <div ref={bottomRef} />
        </>
      )}
    </div>
  );
}

/* ── Welcome screen ──────────────────────────────────────────── */
function WelcomeScreen({ hasDocuments }: { hasDocuments: boolean }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center space-y-8 animate-fade-in">
      {/* Logo cluster */}
      <div className="relative">
        <div className="w-20 h-20 rounded-2xl bg-[var(--bg-card)] border border-[var(--border)]
          flex items-center justify-center brand-glow"
        >
          <Brain className="w-10 h-10 text-[var(--brand)]" />
        </div>
        <div className="absolute -top-2 -right-2 w-7 h-7 bg-[var(--brand-dim)] rounded-lg
          flex items-center justify-center"
        >
          <Zap className="w-4 h-4 text-white" />
        </div>
      </div>

      {/* Headline */}
      <div className="space-y-2">
        <h1 className="font-display text-3xl text-[var(--text-primary)] text-glow">
          Agentic Workflow for Automated Literature Review Assistance
        </h1>
        <p className="text-[var(--text-secondary)]  text-sm">
          A mini research agent for hybrid retrieval, paper summarisation, and
          evidence-backed exploration of engineering research literature.
        </p>
      </div>

      {/* Capability cards */}
      {hasDocuments ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl">
          <CapabilityCard
            icon={<FileSearch className="w-5 h-5" />}
            title="Ask Questions"
            description="Get precise answers grounded in your uploaded papers"
          />
          <CapabilityCard
            icon={<Brain className="w-5 h-5" />}
            title="Summarise Papers"
            description="Get structured summaries with key findings and methodology"
          />
          <CapabilityCard
            icon={<GitCompare className="w-5 h-5" />}
            title="Compare Papers"
            description="Side-by-side comparison of approaches and results"
          />
        </div>
      ) : (
        <div className="border border-dashed border-[var(--border)] rounded-2xl px-8 py-6 max-w-sm">
          <p className="text-[var(--text-muted)] text-sm">
            ← Upload one or more PDF research papers in the sidebar to get started.
          </p>
        </div>
      )}

      {/* Agent pipeline diagram */}
      {hasDocuments && (
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <AgentPill label="Reasoning" color="sky"     />
          <Arrow />
          <AgentPill label="Retrieval" color="violet"  />
          <Arrow />
          <AgentPill label="Document"  color="amber"   />
          <Arrow />
          <AgentPill label="LLM"       color="emerald" />
          <Arrow />
          <AgentPill label="Eval"      color="rose"    />
        </div>
      )}
    </div>
  );
}

function CapabilityCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl p-4 text-left
      hover:border-[var(--brand-dim)] hover:bg-[var(--bg-card-hover)] transition-all duration-200"
    >
      <div className="text-[var(--brand)] mb-2">{icon}</div>
      <p className="text-sm font-medium text-[var(--text-primary)] mb-1">{title}</p>
      <p className="text-xs text-[var(--text-muted)] leading-relaxed">{description}</p>
    </div>
  );
}

function AgentPill({ label, color }: { label: string; color: string }) {
  const colors: Record<string, string> = {
    sky:     "bg-sky-500/10 text-sky-400 border-sky-500/20",
    violet:  "bg-violet-500/10 text-violet-400 border-violet-500/20",
    amber:   "bg-amber-500/10 text-amber-400 border-amber-500/20",
    emerald: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    rose:    "bg-rose-500/10 text-rose-400 border-rose-500/20",
  };
  return (
    <span className={`px-2.5 py-1 rounded-full border text-[10px] font-semibold tracking-wide ${colors[color]}`}>
      {label}
    </span>
  );
}

function Arrow() {
  return <span className="text-[var(--border)] text-lg">→</span>;
}
