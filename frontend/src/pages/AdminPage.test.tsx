import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../components/ToastProvider";
import { AdminPage } from "./AdminPage";

vi.mock("../api/client", () => ({
  fetchAdminAnalytics: vi.fn().mockResolvedValue({
    total_users: 3,
    total_documents: 5,
    total_indexed_chunks: 40,
    total_conversations: 2,
    total_questions: 8,
    completed_ingestion_jobs: 4,
    failed_ingestion_jobs_count: 1,
    average_e2e_latency_ms: 120,
    average_embedding_latency_ms: 20,
    average_vector_search_latency_ms: 15,
    average_llm_latency_ms: 80,
    average_response_latency_ms: 80,
    documents_by_status: [{ status: "completed", count: 4 }],
    documents_by_department: [{ name: "HR", count: 2 }],
    documents_by_category: [{ category: "Policy", count: 2 }],
    questions_over_time: [],
    most_cited_documents: [],
    recent_uploads: [],
    failed_ingestion_jobs: [],
    most_used_categories: [],
    recent_system_errors: [],
    range_start: null,
    range_end: null,
  }),
  fetchAuditLogs: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  fetchIngestionJobs: vi.fn().mockResolvedValue({
    items: [
      {
        id: "job-1",
        document_id: "doc-1",
        status: "completed",
        attempt_number: 1,
        error_message: null,
        embedding_latency_ms: 12,
        duration_ms: 240,
        created_at: new Date().toISOString(),
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
      },
    ],
    total: 1,
  }),
  recoverStaleIngestionJobs: vi.fn(),
}));

describe("AdminPage", () => {
  it("renders live analytics summary and ingestion jobs", async () => {
    render(
      <MemoryRouter>
        <ToastProvider>
          <AdminPage />
        </ToastProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("5")).toBeInTheDocument();
    });
    expect(screen.getByText(/Live metrics from the database/i)).toBeInTheDocument();
    expect(screen.getByText(/Recent ingestion jobs/i)).toBeInTheDocument();
    expect(screen.getAllByText("completed").length).toBeGreaterThan(0);
  });
});
