import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  deleteDocument,
  getDocument,
  getDocumentPreview,
  listDocumentIngestionJobs,
  reprocessDocument,
} from "../api/client";
import { ApiError } from "../api/http";
import { ConfirmBanner } from "../components/ConfirmBanner";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { PipelineProgress } from "../components/PipelineProgress";
import { SkeletonStack } from "../components/SkeletonStack";
import { JobStatusBadge, StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/ToastProvider";
import { useAuth } from "../hooks/useAuth";
import type { DocumentDetail, DocumentPreview, IngestionJob } from "../types";

function formatBytes(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value < 1024) return `${value} B`;
  return `${(value / 1024).toFixed(1)} KB`;
}

function formatMs(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value)} ms`;
}

export function DocumentDetailPage() {
  const { documentId = "" } = useParams();
  const { user } = useAuth();
  const { pushToast } = useToast();
  const navigate = useNavigate();
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const isProcessing =
    document?.processing_status === "pending" || document?.processing_status === "processing";

  async function load() {
    try {
      const [detail, history] = await Promise.all([
        getDocument(documentId),
        listDocumentIngestionJobs(documentId),
      ]);
      setDocument(detail);
      setJobs(history.items);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load document");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);

  useEffect(() => {
    if (!isProcessing) return;
    const timer = window.setInterval(() => {
      void load();
    }, 2000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isProcessing, documentId]);

  async function onLoadPreview() {
    setPreviewOpen(true);
    setPreviewError(null);
    try {
      const result = await getDocumentPreview(documentId);
      setPreview(result);
    } catch (err) {
      setPreviewError(err instanceof ApiError ? err.message : "Preview unavailable");
    }
  }

  async function onReprocess() {
    setBusy(true);
    setError(null);
    try {
      const updated = await reprocessDocument(documentId);
      setDocument(updated);
      pushToast("Reprocess queued. Pipeline will update shortly.", "ok");
      const history = await listDocumentIngestionJobs(documentId);
      setJobs(history.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reprocess failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    setBusy(true);
    try {
      await deleteDocument(documentId);
      navigate("/documents");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
      setBusy(false);
      setConfirmDelete(false);
    }
  }

  if (error && !document) {
    return (
      <section className="panel">
        <ErrorBanner message={error} onRetry={() => void load()} />
        <Link className="text-link" to="/documents">
          ← Back to documents
        </Link>
      </section>
    );
  }

  if (!document) {
    return (
      <section className="panel">
        <SkeletonStack label="Loading document" />
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{document.title}</h2>
          <p className="muted">
            {document.department} · {document.category}
          </p>
        </div>
        <StatusBadge status={document.processing_status} stage={document.ingestion_stage} />
      </div>

      <h3>Ingestion pipeline</h3>
      <PipelineProgress stage={document.ingestion_stage} />

      {user?.role === "admin" && document.processing_error && (
        <ErrorBanner message={document.processing_error}>
          {document.latest_ingestion_job?.error_message && (
            <p className="muted">Job detail: {document.latest_ingestion_job.error_message}</p>
          )}
        </ErrorBanner>
      )}
      {error && <ErrorBanner message={error} />}

      <dl className="meta-grid">
        <div>
          <dt>Current version</dt>
          <dd>v{document.current_version}</dd>
        </div>
        <div>
          <dt>File type</dt>
          <dd>{document.file_type?.toUpperCase() ?? "—"}</dd>
        </div>
        <div>
          <dt>File size</dt>
          <dd>{formatBytes(document.file_size_bytes)}</dd>
        </div>
        <div>
          <dt>Page count</dt>
          <dd>{document.page_count ?? "—"}</dd>
        </div>
        <div>
          <dt>Chunk count</dt>
          <dd>{document.chunk_count}</dd>
        </div>
        <div>
          <dt>Embedding count</dt>
          <dd>{document.embedding_count}</dd>
        </div>
        <div>
          <dt>Uploaded by</dt>
          <dd>
            {document.uploaded_by
              ? `${document.uploaded_by.full_name} (${document.uploaded_by.email})`
              : document.uploaded_by_id}
          </dd>
        </div>
        <div>
          <dt>Uploaded</dt>
          <dd>{new Date(document.created_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt>Latest job</dt>
          <dd>
            {document.latest_ingestion_job
              ? `${document.latest_ingestion_job.status} (attempt ${document.latest_ingestion_job.attempt_number})`
              : "—"}
          </dd>
        </div>
      </dl>

      <div className="button-row">
        <button className="btn" type="button" onClick={() => void onLoadPreview()}>
          {previewOpen ? "Refresh preview" : "Show text preview"}
        </button>
        {user?.role === "admin" && (
          <>
            <button className="btn" type="button" disabled={busy || isProcessing} onClick={() => void onReprocess()}>
              Reprocess
            </button>
            <button
              className="btn danger"
              type="button"
              disabled={busy}
              onClick={() => setConfirmDelete(true)}
            >
              Delete
            </button>
          </>
        )}
      </div>

      {confirmDelete && (
        <ConfirmBanner
          title={`Delete “${document.title}” and all stored versions?`}
          confirmLabel="Confirm delete"
          busy={busy}
          onConfirm={() => void onDelete()}
          onCancel={() => setConfirmDelete(false)}
        >
          This cannot be undone.
        </ConfirmBanner>
      )}

      {previewOpen && (
        <div className="preview-panel">
          <h3>Document preview</h3>
          {previewError && <ErrorBanner message={previewError} />}
          {!preview && !previewError && <p className="muted">Loading preview…</p>}
          {preview && (
            <>
              <p className="muted">
                Showing extracted text ({preview.chunk_count} chunks
                {preview.page_count != null ? `, ${preview.page_count} pages` : ""})
              </p>
              <pre className="preview-text">{preview.preview_text || "No extracted text yet."}</pre>
            </>
          )}
        </div>
      )}

      <h3>Version history</h3>
      <div className="table-wrap responsive-table-desktop">
        <table className="data-table">
          <thead>
            <tr>
              <th>Version</th>
              <th>Filename</th>
              <th>Type</th>
              <th>Size</th>
              <th>Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {document.versions.map((version) => (
              <tr key={version.id}>
                <td>v{version.version_number}</td>
                <td>{version.original_filename}</td>
                <td>{version.file_type.toUpperCase()}</td>
                <td>{formatBytes(version.file_size_bytes)}</td>
                <td>{new Date(version.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="responsive-card-list">
        {document.versions.map((version) => (
          <article key={version.id} className="doc-card">
            <div className="doc-card-header">
              <strong>v{version.version_number}</strong>
              <span className="muted">{version.file_type.toUpperCase()}</span>
            </div>
            <p className="muted">
              {version.original_filename} · {formatBytes(version.file_size_bytes)}
            </p>
            <p className="muted">{new Date(version.created_at).toLocaleString()}</p>
          </article>
        ))}
      </div>

      <h3>Ingestion attempts</h3>
      <p className="muted">
        Each reprocess creates a new attempt. Failed jobs keep admin-visible error details for
        debugging.
      </p>
      <div className="table-wrap responsive-table-desktop">
        <table className="data-table">
          <thead>
            <tr>
              <th>Attempt</th>
              <th>Status</th>
              <th>Duration</th>
              <th>Started</th>
              <th>Finished</th>
              {user?.role === "admin" && <th>Error</th>}
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.attempt_number}</td>
                <td>
                  <JobStatusBadge status={job.status} />
                </td>
                <td>{formatMs(job.duration_ms)}</td>
                <td>{job.started_at ? new Date(job.started_at).toLocaleString() : "—"}</td>
                <td>{job.completed_at ? new Date(job.completed_at).toLocaleString() : "—"}</td>
                {user?.role === "admin" && <td>{job.error_message ?? "—"}</td>}
              </tr>
            ))}
            {!jobs.length && (
              <tr>
                <td colSpan={user?.role === "admin" ? 6 : 5} className="muted">
                  No ingestion jobs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="responsive-card-list">
        {jobs.map((job) => (
          <article key={job.id} className="doc-card">
            <div className="doc-card-header">
              <strong>Attempt {job.attempt_number}</strong>
              <JobStatusBadge status={job.status} />
            </div>
            <p className="muted">
              {formatMs(job.duration_ms)} ·{" "}
              {job.started_at ? new Date(job.started_at).toLocaleString() : "Not started"}
            </p>
            {user?.role === "admin" && job.error_message && (
              <p className="error">{job.error_message}</p>
            )}
          </article>
        ))}
        {!jobs.length && <EmptyState title="No ingestion jobs yet">Upload or reprocess to create an attempt.</EmptyState>}
      </div>

      <Link className="text-link" to="/documents">
        ← Back to documents
      </Link>
    </section>
  );
}
