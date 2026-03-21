"use client";

// components/layout/Sidebar.tsx
// Left panel: upload control + indexed document list

import { useState, useCallback, useRef } from "react";
import {
  Upload, FileText, Trash2, Loader2, CheckCircle2,
  AlertCircle, ChevronDown, ChevronUp, Cpu, X,
} from "lucide-react";
import { DocumentInfo } from "@/types";
import { uploadPDF, deleteDocument } from "@/lib/api";

interface SidebarProps {
  documents:     DocumentInfo[];
  onDocumentsChange: (docs: DocumentInfo[]) => void;
  selectedDocs:  string[];
  onSelectDocs:  (ids: string[]) => void;
}

type UploadStatus = "idle" | "uploading" | "success" | "error";

export default function Sidebar({
  documents,
  onDocumentsChange,
  selectedDocs,
  onSelectDocs,
}: SidebarProps) {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>("idle");
  const [uploadMsg,    setUploadMsg]    = useState("");
  const [dragOver,     setDragOver]     = useState(false);
  const [expanded,     setExpanded]     = useState<Set<string>>(new Set());
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Upload handler ──────────────────────────────────────────────────────
  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files?.length) return;
      const pdfFiles = Array.from(files).filter((f) => f.type === "application/pdf");
      if (!pdfFiles.length) {
        setUploadStatus("error");
        setUploadMsg("Only PDF files are accepted.");
        return;
      }

      setUploadStatus("uploading");
      setUploadMsg(`Uploading ${pdfFiles.length} file(s)…`);

      const newDocs: DocumentInfo[] = [...documents];
      let errored = 0;

      for (const file of pdfFiles) {
        try {
          const res = await uploadPDF(file);
          newDocs.push({
            doc_id:     res.doc_id,
            filename:   res.filename,
            num_pages:  0,
            num_chunks: res.num_chunks,
          });
        } catch (err: unknown) {
          errored++;
          console.error("Upload failed:", err);
        }
      }

      onDocumentsChange(newDocs);

      if (errored) {
        setUploadStatus("error");
        setUploadMsg(`${errored} file(s) failed to upload.`);
      } else {
        setUploadStatus("success");
        setUploadMsg(`${pdfFiles.length} paper(s) indexed successfully.`);
        setTimeout(() => setUploadStatus("idle"), 3500);
      }
    },
    [documents, onDocumentsChange]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  // ── Delete document ─────────────────────────────────────────────────────
  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(docId);
      onDocumentsChange(documents.filter((d) => d.doc_id !== docId));
      onSelectDocs(selectedDocs.filter((id) => id !== docId));
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  // ── Toggle selection ────────────────────────────────────────────────────
  const toggleSelect = (docId: string) => {
    if (selectedDocs.includes(docId)) {
      onSelectDocs(selectedDocs.filter((id) => id !== docId));
    } else {
      onSelectDocs([...selectedDocs, docId]);
    }
  };

  const toggleExpand = (docId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(docId) ? next.delete(docId) : next.add(docId);
      return next;
    });
  };

  return (
    <aside className="flex flex-col h-full w-72 border-r border-[var(--border)] bg-[var(--bg-card)]">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="px-5 pt-6 pb-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-2 mb-1">
          <Cpu className="w-5 h-5 text-[var(--brand)]" />
          <span className="font-display text-lg text-[var(--text-primary)] tracking-tight">
            MedRAG
          </span>
        </div>
        <p className="text-xs text-[var(--text-muted)]">
          Healthcare Research Intelligence
        </p>
      </div>

      {/* ── Upload zone ────────────────────────────────────────── */}
      <div className="px-4 py-4 border-b border-[var(--border)]">
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`
            relative flex flex-col items-center justify-center gap-2
            p-5 rounded-xl border-2 border-dashed cursor-pointer
            transition-all duration-200
            ${dragOver
              ? "border-[var(--brand)] bg-[var(--brand-glow)]"
              : "border-[var(--border)] hover:border-[var(--brand-dim)] hover:bg-[var(--bg-card-hover)]"
            }
          `}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />

          {uploadStatus === "uploading" ? (
            <Loader2 className="w-7 h-7 text-[var(--brand)] animate-spin" />
          ) : (
            <Upload className="w-7 h-7 text-[var(--text-muted)]" />
          )}

          <div className="text-center">
            <p className="text-sm font-medium text-[var(--text-secondary)]">
              {uploadStatus === "uploading" ? "Processing…" : "Upload Research Papers"}
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Drop PDFs here or click to browse
            </p>
          </div>
        </div>

        {/* Status message */}
        {uploadStatus !== "idle" && uploadStatus !== "uploading" && (
          <div
            className={`mt-2 flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg
              ${uploadStatus === "success"
                ? "bg-emerald-500/10 text-emerald-400"
                : "bg-red-500/10 text-red-400"
              }`}
          >
            {uploadStatus === "success"
              ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              : <AlertCircle  className="w-3.5 h-3.5 shrink-0" />
            }
            {uploadMsg}
          </div>
        )}
      </div>

      {/* ── Document list ───────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1.5">
        {documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-center">
            <FileText className="w-8 h-8 text-[var(--text-muted)] mb-2 opacity-40" />
            <p className="text-xs text-[var(--text-muted)]">No papers indexed yet</p>
          </div>
        ) : (
          <>
            <p className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider px-2 mb-2">
              {documents.length} Paper{documents.length !== 1 ? "s" : ""} Indexed
            </p>
            {documents.map((doc) => {
              const isSelected = selectedDocs.includes(doc.doc_id);
              const isExpanded = expanded.has(doc.doc_id);
              return (
                <div
                  key={doc.doc_id}
                  className={`rounded-xl border transition-all duration-150 overflow-hidden
                    ${isSelected
                      ? "border-[var(--brand-dim)] bg-[rgba(56,189,248,0.06)]"
                      : "border-[var(--border-subtle)] bg-[var(--bg-card-hover)] hover:border-[var(--border)]"
                    }`}
                >
                  {/* Card header */}
                  <div className="flex items-start gap-2 p-3">
                    {/* Selection checkbox */}
                    <button
                      onClick={() => toggleSelect(doc.doc_id)}
                      className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors
                        ${isSelected
                          ? "bg-[var(--brand-dim)] border-[var(--brand-dim)]"
                          : "border-[var(--border)] hover:border-[var(--brand-dim)]"
                        }`}
                    >
                      {isSelected && (
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                          <path d="M2 5l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </button>

                    {/* Doc name */}
                    <div className="flex-1 min-w-0">
                      <p
                        className="text-xs font-medium text-[var(--text-primary)] truncate cursor-pointer"
                        title={doc.filename}
                        onClick={() => toggleExpand(doc.doc_id)}
                      >
                        {doc.filename}
                      </p>
                      <p className="text-xs text-[var(--text-muted)] mt-0.5">
                        {doc.num_chunks} chunks
                        {doc.num_pages > 0 ? ` · ${doc.num_pages} pages` : ""}
                      </p>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => toggleExpand(doc.doc_id)}
                        className="p-1 text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
                      >
                        {isExpanded
                          ? <ChevronUp className="w-3.5 h-3.5" />
                          : <ChevronDown className="w-3.5 h-3.5" />
                        }
                      </button>
                      <button
                        onClick={() => handleDelete(doc.doc_id)}
                        className="p-1 text-[var(--text-muted)] hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="px-3 pb-3 pt-0 border-t border-[var(--border-subtle)]">
                      <div className="mt-2 space-y-1">
                        <DetailRow label="File" value={doc.filename} />
                        <DetailRow label="Chunks" value={String(doc.num_chunks)} />
                        {doc.num_pages > 0 && (
                          <DetailRow label="Pages" value={String(doc.num_pages)} />
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* ── Selection hint ─────────────────────────────────────── */}
      {selectedDocs.length > 0 && (
        <div className="px-4 py-3 border-t border-[var(--border)] bg-[rgba(56,189,248,0.04)]">
          <div className="flex items-center justify-between">
            <p className="text-xs text-[var(--brand)]">
              {selectedDocs.length} paper{selectedDocs.length !== 1 ? "s" : ""} selected
            </p>
            <button
              onClick={() => onSelectDocs([])}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] flex items-center gap-1"
            >
              <X className="w-3 h-3" /> Clear
            </button>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Queries will be scoped to selected papers
          </p>
        </div>
      )}
    </aside>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-[var(--text-muted)]">{label}</span>
      <span className="text-[var(--text-secondary)] truncate max-w-[140px]" title={value}>
        {value}
      </span>
    </div>
  );
}
