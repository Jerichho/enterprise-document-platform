import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  fetchAdminAnalytics,
  fetchAuditLogs,
  fetchIngestionJobs,
  recoverStaleIngestionJobs,
  type AdminAnalytics,
} from "../api/client";
import { ApiError } from "../api/http";
import { ConfirmBanner } from "../components/ConfirmBanner";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { SimpleBarChart } from "../components/SimpleBarChart";
import { SkeletonStack } from "../components/SkeletonStack";
import { JobStatusBadge, StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/ToastProvider";
import type { ProcessingStatus } from "../types";

type JobRow = {
  id: string;
  document_id: string;
  status: string;
  attempt_number: number;
  error_message: string | null;
  embedding_latency_ms: number | null;
  duration_ms: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

function toInputDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function startOfDayIso(dateValue: string): string {
  return `${dateValue}T00:00:00.000Z`;
}

function endOfDayIso(dateValue: string): string {
  return `${dateValue}T23:59:59.999Z`;
}

function formatMs(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value)} ms`;
}

export function AdminPage() {
  const { pushToast } = useToast();
  const today = useMemo(() => new Date(), []);
  const defaultStart = useMemo(() => {
    const start = new Date(today);
    start.setUTCDate(start.getUTCDate() - 29);
    return toInputDate(start);
  }, [today]);

  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(toInputDate(today));
  const [analytics, setAnalytics] = useState<AdminAnalytics | null>(null);
  const [auditItems, setAuditItems] = useState<
    Array<{
      id: string;
      action: string;
      success: boolean;
      error_message: string | null;
      created_at: string;
    }>
  >([]);
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [jobStatusFilter, setJobStatusFilter] = useState("");
  const [jobAutoRefresh, setJobAutoRefresh] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [recoverBusy, setRecoverBusy] = useState(false);
  const [confirmRecover, setConfirmRecover] = useState(false);

  const loadJobs = useCallback(async () => {
    const ingestion = await fetchIngestionJobs({
      status: jobStatusFilter || undefined,
      limit: 30,
    });
    setJobs(ingestion.items);
  }, [jobStatusFilter]);

  async function load(rangeStart = startDate, rangeEnd = endDate) {
    setLoading(true);
    setError(null);
    try {
      const [stats, audits] = await Promise.all([
        fetchAdminAnalytics({
          start: startOfDayIso(rangeStart),
          end: endOfDayIso(rangeEnd),
        }),
        fetchAuditLogs(1),
      ]);
      setAnalytics(stats);
      setAuditItems(audits.items);
      await loadJobs();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void loadJobs().catch(() => {
      /* surface via next full load */
    });
  }, [loadJobs]);

  useEffect(() => {
    if (!jobAutoRefresh) return;
    const hasActive = jobs.some((job) => job.status === "pending" || job.status === "running");
    if (!hasActive) return;
    const timer = window.setInterval(() => {
      void loadJobs();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [jobAutoRefresh, jobs, loadJobs]);

  async function onRecoverStale() {
    setRecoverBusy(true);
    try {
      const result = await recoverStaleIngestionJobs();
      const message =
        result.recovered === 0
          ? `No stale jobs (timeout ${result.stale_after_minutes}m).`
          : `Recovered ${result.recovered} stale job(s). Reprocess those documents to retry.`;
      pushToast(message, result.recovered === 0 ? "warn" : "ok");
      await loadJobs();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to recover stale jobs");
    } finally {
      setRecoverBusy(false);
      setConfirmRecover(false);
    }
  }

  const statusCount = (status: ProcessingStatus) =>
    analytics?.documents_by_status.find((item) => item.status === status)?.count ?? 0;

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Admin</h2>
          <p className="muted">
            Live metrics from the database. Latency values are measured timings, not estimates.
          </p>
        </div>
        <Link className="btn primary" to="/admin/upload">
          Upload document
        </Link>
      </div>

      <form
        className="admin-range-form"
        onSubmit={(event) => {
          event.preventDefault();
          void load();
        }}
      >
        <label>
          From
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </label>
        <label>
          To
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </label>
        <button className="btn" type="submit" disabled={loading}>
          Apply range
        </button>
      </form>

      {error && <ErrorBanner message={error} onRetry={() => void load()} />}
      {loading && !analytics && <SkeletonStack label="Loading analytics" />}

      {analytics && (
        <>
          <p className="muted">
            Showing activity from {new Date(analytics.range_start ?? startDate).toLocaleDateString()}{" "}
            to {new Date(analytics.range_end ?? endDate).toLocaleDateString()}. Inventory totals are
            lifetime counts.
          </p>

          <div className="stat-row">
            <article>
              <h3>{analytics.total_users}</h3>
              <p>Users</p>
            </article>
            <article>
              <h3>{analytics.total_documents}</h3>
              <p>Documents</p>
            </article>
            <article>
              <h3>{analytics.total_indexed_chunks}</h3>
              <p>Indexed chunks</p>
            </article>
            <article>
              <h3>{analytics.total_conversations}</h3>
              <p>Conversations</p>
            </article>
          </div>

          <div className="stat-row">
            <article>
              <h3>{analytics.total_questions}</h3>
              <p>Questions (range)</p>
            </article>
            <article>
              <h3>{analytics.completed_ingestion_jobs}</h3>
              <p>Completed jobs</p>
            </article>
            <article>
              <h3>{analytics.failed_ingestion_jobs_count}</h3>
              <p>Failed jobs</p>
            </article>
            <article>
              <h3>{statusCount("completed")}</h3>
              <p>Completed docs</p>
            </article>
          </div>

          <div className="stat-row">
            <article>
              <h3>{formatMs(analytics.average_e2e_latency_ms)}</h3>
              <p>Avg end-to-end</p>
            </article>
            <article>
              <h3>{formatMs(analytics.average_embedding_latency_ms)}</h3>
              <p>Avg embedding</p>
            </article>
            <article>
              <h3>{formatMs(analytics.average_vector_search_latency_ms)}</h3>
              <p>Avg vector search</p>
            </article>
            <article>
              <h3>{formatMs(analytics.average_llm_latency_ms)}</h3>
              <p>Avg LLM</p>
            </article>
          </div>

          <div className="admin-grid">
            <section>
              <h3>Questions over time</h3>
              <SimpleBarChart
                items={analytics.questions_over_time.map((item) => ({
                  label: item.date.slice(5),
                  value: item.count,
                }))}
              />
            </section>
            <section>
              <h3>Documents by department</h3>
              <SimpleBarChart
                items={analytics.documents_by_department.map((item) => ({
                  label: item.name,
                  value: item.count,
                }))}
              />
            </section>
            <section>
              <h3>Documents by category</h3>
              <SimpleBarChart
                items={analytics.documents_by_category.map((item) => ({
                  label: item.category,
                  value: item.count,
                }))}
              />
            </section>
            <section>
              <h3>Most cited documents</h3>
              <SimpleBarChart
                items={analytics.most_cited_documents.map((item) => ({
                  label: item.document_title,
                  value: item.citation_count,
                }))}
                emptyLabel="No citations in this range."
              />
            </section>
          </div>

          <h3>Recent uploads</h3>
          <div className="table-wrap responsive-table-desktop">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Department</th>
                  <th>Status</th>
                  <th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {analytics.recent_uploads.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <Link to={`/documents/${doc.id}`}>{doc.title}</Link>
                    </td>
                    <td>{doc.department}</td>
                    <td>
                      <StatusBadge status={doc.processing_status as ProcessingStatus} />
                    </td>
                    <td>{new Date(doc.created_at).toLocaleString()}</td>
                  </tr>
                ))}
                {!analytics.recent_uploads.length && (
                  <tr>
                    <td colSpan={4} className="muted">
                      No uploads in this range.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="responsive-card-list">
            {analytics.recent_uploads.map((doc) => (
              <article key={doc.id} className="doc-card">
                <div className="doc-card-header">
                  <Link to={`/documents/${doc.id}`}>{doc.title}</Link>
                  <StatusBadge status={doc.processing_status as ProcessingStatus} />
                </div>
                <p className="muted">
                  {doc.department} · {new Date(doc.created_at).toLocaleString()}
                </p>
              </article>
            ))}
            {!analytics.recent_uploads.length && (
              <EmptyState title="No uploads in this range">
                Try widening the date filter or upload a document.
              </EmptyState>
            )}
          </div>

          <h3>Recent ingestion failures</h3>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Attempt</th>
                  <th>Error</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {analytics.failed_ingestion_jobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <Link to={`/documents/${job.document_id}`}>{job.document_id.slice(0, 8)}…</Link>
                    </td>
                    <td>{job.attempt_number}</td>
                    <td>{job.error_message ?? "—"}</td>
                    <td>{new Date(job.created_at).toLocaleString()}</td>
                  </tr>
                ))}
                {!analytics.failed_ingestion_jobs.length && (
                  <tr>
                    <td colSpan={4} className="muted">
                      No failed jobs in this range.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3>Recent ingestion jobs</h3>
      <div className="admin-jobs-toolbar">
        <label>
          Status
          <select value={jobStatusFilter} onChange={(e) => setJobStatusFilter(e.target.value)}>
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </label>
        <label className="status-toggle">
          <input
            type="checkbox"
            checked={jobAutoRefresh}
            onChange={(e) => setJobAutoRefresh(e.target.checked)}
          />
          Auto-refresh active jobs
        </label>
        <button className="btn" type="button" onClick={() => void loadJobs()}>
          Refresh jobs
        </button>
        <button
          className="btn ghost"
          type="button"
          disabled={recoverBusy}
          onClick={() => setConfirmRecover(true)}
        >
          Recover stale jobs
        </button>
      </div>
      {confirmRecover && (
        <ConfirmBanner
          title="Recover stale ingestion jobs?"
          confirmLabel="Recover"
          busy={recoverBusy}
          onConfirm={() => void onRecoverStale()}
          onCancel={() => setConfirmRecover(false)}
        >
          Jobs stuck in pending/running longer than the configured timeout will be marked failed so
          documents can be reprocessed.
        </ConfirmBanner>
      )}
      <div className="table-wrap responsive-table-desktop">
        <table className="data-table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Status</th>
              <th>Attempt</th>
              <th>Duration</th>
              <th>Embed</th>
              <th>Error</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>
                  <Link to={`/documents/${job.document_id}`}>{job.document_id.slice(0, 8)}…</Link>
                </td>
                <td>
                  <JobStatusBadge status={job.status} />
                </td>
                <td>{job.attempt_number}</td>
                <td>{formatMs(job.duration_ms)}</td>
                <td>{formatMs(job.embedding_latency_ms)}</td>
                <td>{job.error_message ?? "—"}</td>
                <td>{new Date(job.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {!jobs.length && (
              <tr>
                <td colSpan={7} className="muted">
                  No ingestion jobs match this filter.
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
              <Link to={`/documents/${job.document_id}`}>{job.document_id.slice(0, 8)}…</Link>
              <JobStatusBadge status={job.status} />
            </div>
            <p className="muted">
              Attempt {job.attempt_number} · {formatMs(job.duration_ms)} ·{" "}
              {new Date(job.created_at).toLocaleString()}
            </p>
            {job.error_message && <p className="error">{job.error_message}</p>}
          </article>
        ))}
        {!jobs.length && (
          <EmptyState title="No ingestion jobs">No jobs match this status filter.</EmptyState>
        )}
      </div>

      <h3>Recent audit events</h3>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Action</th>
              <th>Result</th>
              <th>Error</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {auditItems.map((item) => (
              <tr key={item.id}>
                <td>{item.action}</td>
                <td>
                  <JobStatusBadge status={item.success ? "ok" : "failed"} />
                </td>
                <td>{item.error_message ?? "—"}</td>
                <td>{new Date(item.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {!auditItems.length && (
              <tr>
                <td colSpan={4} className="muted">
                  No audit events yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
