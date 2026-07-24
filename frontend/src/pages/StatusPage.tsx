import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchHealth, fetchReady } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { SkeletonStack } from "../components/SkeletonStack";
import { JobStatusBadge, ToneBadge } from "../components/StatusBadge";
import type { HealthResponse, ReadyResponse } from "../types";

type LoadState = "idle" | "loading" | "success" | "error";

const CHECK_LABELS: Record<string, string> = {
  database: "PostgreSQL",
  pgvector: "pgvector extension",
  storage: "Document storage",
  llm_provider: "LLM provider",
  embedding_provider: "Embedding provider",
};

export function StatusPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const load = useCallback(async () => {
    setState("loading");
    setError(null);
    try {
      const [healthResult, readyResult] = await Promise.all([fetchHealth(), fetchReady()]);
      setHealth(healthResult);
      setReady(readyResult);
      setUpdatedAt(new Date());
      setState("success");
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : "Failed to reach API");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = window.setInterval(() => {
      void load();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, load]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>System status</h2>
          <p className="muted">
            Liveness and readiness probes. Sensitive configuration values are never returned.
          </p>
        </div>
        <div className="button-row">
          <label className="status-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh
          </label>
          <button className="btn" type="button" onClick={() => void load()} disabled={state === "loading"}>
            Refresh
          </button>
        </div>
      </div>

      {state === "loading" && !health && <SkeletonStack rows={3} label="Checking services" />}
      {state === "error" && error && <ErrorBanner message={error} onRetry={() => void load()} />}

      {health && (
        <dl className="meta-grid">
          <div>
            <dt>Liveness</dt>
            <dd>
              <ToneBadge tone="ok">{health.status}</ToneBadge>
            </dd>
          </div>
          <div>
            <dt>Service</dt>
            <dd>{health.service}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>{health.version}</dd>
          </div>
          <div>
            <dt>Environment</dt>
            <dd>{health.environment}</dd>
          </div>
          <div>
            <dt>Last checked</dt>
            <dd>{updatedAt ? updatedAt.toLocaleTimeString() : "—"}</dd>
          </div>
        </dl>
      )}

      {ready && (
        <>
          <div className="status-ready-banner">
            <JobStatusBadge status={ready.status} />
            <p className="muted">
              {ready.status === "ready" && "All required and optional dependencies are healthy."}
              {ready.status === "degraded" &&
                "Core dependencies are up, but one or more AI providers are unavailable. Non-RAG routes remain usable."}
              {ready.status === "not_ready" &&
                "A required dependency is down. The API should not receive traffic until this recovers."}
            </p>
          </div>

          <div className="status-check-grid">
            {ready.checks.map((check) => (
              <article key={check.name} className="status-check-card">
                <header>
                  <strong>{CHECK_LABELS[check.name] ?? check.name}</strong>
                  <JobStatusBadge status={check.status} />
                </header>
                <p className="muted">{check.detail ?? "No additional detail."}</p>
              </article>
            ))}
          </div>
        </>
      )}

      <p className="muted">
        Latency trends for embedding, retrieval, and LLM calls are available on the{" "}
        <Link to="/admin">Admin analytics</Link> page.
      </p>
    </section>
  );
}
