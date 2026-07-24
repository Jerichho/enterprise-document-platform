import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { listDocuments } from "../api/client";
import { ApiError } from "../api/http";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { SkeletonStack } from "../components/SkeletonStack";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../hooks/useAuth";
import type { DocumentSummary, ProcessingStatus } from "../types";

const PAGE_SIZE = 10;

function formatBytes(value: number | null): string {
  if (value == null) return "—";
  if (value < 1024) return `${value} B`;
  return `${(value / 1024).toFixed(1)} KB`;
}

export function DocumentsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [department, setDepartment] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState<"" | ProcessingStatus>("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasActiveProcessing = useMemo(
    () => items.some((doc) => doc.processing_status === "pending" || doc.processing_status === "processing"),
    [items],
  );

  async function load(options?: {
    page?: number;
    q?: string;
    department?: string;
    category?: string;
    status?: "" | ProcessingStatus;
    sortBy?: string;
    sortOrder?: "asc" | "desc";
  }) {
    const nextPage = options?.page ?? page;
    const nextQ = options?.q ?? q;
    const nextDept = options?.department ?? department;
    const nextCategory = options?.category ?? category;
    const nextStatus = options?.status ?? status;
    const nextSortBy = options?.sortBy ?? sortBy;
    const nextSortOrder = options?.sortOrder ?? sortOrder;

    setLoading(true);
    setError(null);
    try {
      const result = await listDocuments({
        page: nextPage,
        page_size: PAGE_SIZE,
        q: nextQ || undefined,
        department: nextDept || undefined,
        category: nextCategory || undefined,
        status: nextStatus || undefined,
        sort_by: nextSortBy,
        sort_order: nextSortOrder,
      });
      setItems(result.items);
      setTotal(result.total);
      setPage(result.page);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load({ page: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!hasActiveProcessing) return;
    const timer = window.setInterval(() => {
      void load();
    }, 2500);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasActiveProcessing, page, q, department, category, status, sortBy, sortOrder]);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    void load({ page: 1 });
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Documents</h2>
          <p className="muted">{total} documents in the knowledge base</p>
        </div>
        {user?.role === "admin" && (
          <Link className="btn primary" to="/admin/upload">
            Upload
          </Link>
        )}
      </div>

      <form className="docs-filters" onSubmit={onSearch}>
        <label>
          Search
          <input
            placeholder="Title, department, category, or text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
        <label>
          Department
          <input value={department} onChange={(e) => setDepartment(e.target.value)} />
        </label>
        <label>
          Category
          <input value={category} onChange={(e) => setCategory(e.target.value)} />
        </label>
        <label>
          Status
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as "" | ProcessingStatus)}
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </label>
        <label>
          Sort by
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="created_at">Uploaded</option>
            <option value="updated_at">Updated</option>
            <option value="title">Title</option>
            <option value="department">Department</option>
            <option value="category">Category</option>
            <option value="processing_status">Status</option>
          </select>
        </label>
        <label>
          Order
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as "asc" | "desc")}
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </label>
        <button className="btn" type="submit">
          Apply
        </button>
      </form>

      {error && <ErrorBanner message={error} onRetry={() => void load()} />}

      {loading && <SkeletonStack label="Loading documents" />}

      {!loading && items.length === 0 && (
        <EmptyState title="No documents found">
          {user?.role === "admin"
            ? "Upload a policy document to start building the knowledge base."
            : "Ask an administrator to upload company documents."}
        </EmptyState>
      )}

      {!loading && items.length > 0 && (
        <>
          <div className="table-wrap docs-table-desktop">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Department</th>
                  <th>Category</th>
                  <th>Type</th>
                  <th>Size</th>
                  <th>Chunks</th>
                  <th>Status</th>
                  <th>Version</th>
                  <th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {items.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <Link to={`/documents/${doc.id}`}>{doc.title}</Link>
                    </td>
                    <td>{doc.department}</td>
                    <td>{doc.category}</td>
                    <td>{doc.file_type?.toUpperCase() ?? "—"}</td>
                    <td>{formatBytes(doc.file_size_bytes)}</td>
                    <td>{doc.chunk_count}</td>
                    <td>
                      <StatusBadge status={doc.processing_status} stage={doc.ingestion_stage} />
                    </td>
                    <td>v{doc.current_version}</td>
                    <td>{new Date(doc.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="docs-card-list">
            {items.map((doc) => (
              <article key={doc.id} className="doc-card">
                <div className="doc-card-header">
                  <Link to={`/documents/${doc.id}`}>{doc.title}</Link>
                  <StatusBadge status={doc.processing_status} stage={doc.ingestion_stage} />
                </div>
                <p className="muted">
                  {doc.department} · {doc.category} · v{doc.current_version}
                </p>
                <p className="muted">
                  {doc.file_type?.toUpperCase() ?? "FILE"} · {formatBytes(doc.file_size_bytes)} ·{" "}
                  {doc.chunk_count} chunks
                </p>
              </article>
            ))}
          </div>

          <div className="pagination-row">
            <button
              className="btn ghost"
              type="button"
              disabled={page <= 1 || loading}
              onClick={() => void load({ page: page - 1 })}
            >
              Previous
            </button>
            <span className="muted">
              Page {page} of {totalPages}
            </span>
            <button
              className="btn ghost"
              type="button"
              disabled={page >= totalPages || loading}
              onClick={() => void load({ page: page + 1 })}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}
