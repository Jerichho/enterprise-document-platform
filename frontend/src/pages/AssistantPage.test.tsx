import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssistantPage } from "./AssistantPage";

const askQuestion = vi.fn();
const listConversations = vi.fn();
const listDocuments = vi.fn();
const fetchReady = vi.fn();
const createConversation = vi.fn();
const getConversation = vi.fn();

vi.mock("../api/client", () => ({
  askQuestion: (...args: unknown[]) => askQuestion(...args),
  listConversations: (...args: unknown[]) => listConversations(...args),
  listDocuments: (...args: unknown[]) => listDocuments(...args),
  fetchReady: (...args: unknown[]) => fetchReady(...args),
  createConversation: (...args: unknown[]) => createConversation(...args),
  getConversation: (...args: unknown[]) => getConversation(...args),
  deleteConversation: vi.fn(),
}));

describe("AssistantPage answer presentation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listConversations.mockResolvedValue({ items: [], total: 0 });
    listDocuments.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
    fetchReady.mockResolvedValue({
      status: "ready",
      environment: "development",
      version: "0.1.0",
      demo_mode: true,
      llm_provider: "fake",
      embedding_provider: "fake",
      checks: [],
    });
  });

  it("shows the demo provider banner and hides suggestions without documents", async () => {
    render(
      <MemoryRouter>
        <AssistantPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/Demo provider active/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/phishing/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Upload and finish indexing/i)).toBeInTheDocument();
  });

  it("renders suggestions derived from indexed documents", async () => {
    listDocuments.mockResolvedValue({
      items: [
        {
          id: "doc-1",
          title: "PTO Policy",
          department: "HR",
          category: "Benefits",
          current_version: 1,
          processing_status: "completed",
          ingestion_stage: "completed",
          processing_error: null,
          embedding_provider: "fake",
          uploaded_by_id: "u1",
          file_type: "txt",
          file_size_bytes: 100,
          chunk_count: 1,
          created_at: "2026-07-20T12:00:00Z",
          updated_at: "2026-07-20T12:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });

    render(
      <MemoryRouter>
        <AssistantPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: /How many PTO days/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /phishing/i })).not.toBeInTheDocument();
  });

  it("renders a clean answer with citations and collapsed retrieval details", async () => {
    listConversations.mockResolvedValue({
      items: [
        {
          id: "conv-1",
          title: "PTO",
          created_at: "2026-07-20T12:00:00Z",
          updated_at: "2026-07-20T12:00:00Z",
        },
      ],
      total: 1,
    });
    getConversation.mockResolvedValue({
      id: "conv-1",
      title: "PTO",
      created_at: "2026-07-20T12:00:00Z",
      updated_at: "2026-07-20T12:00:00Z",
      messages: [
        {
          id: "m1",
          role: "user",
          content: "How many PTO days?",
          retrieval_top_k: null,
          retrieval_min_score: null,
          max_retrieval_score: null,
          grounded: null,
          insufficient_context: null,
          llm_latency_ms: null,
          llm_model: null,
          created_at: "2026-07-20T12:00:00Z",
          citations: [],
        },
        {
          id: "m2",
          role: "assistant",
          content: "Full-time employees receive 20 days of PTO each calendar year.",
          retrieval_top_k: 5,
          retrieval_min_score: 0.5,
          max_retrieval_score: 0.81,
          grounded: true,
          insufficient_context: false,
          answer_status: "grounded",
          llm_latency_ms: 12,
          llm_model: "fake-llm",
          created_at: "2026-07-20T12:00:01Z",
          citations: [
            {
              id: "c1",
              chunk_id: "chunk-1",
              document_id: "doc-1",
              document_title: "PTO Policy",
              page_number: 1,
              chunk_index: 0,
              relevance_score: 0.81,
              rank: 1,
              snippet: "Employees receive twenty days of paid time off.",
            },
          ],
          retrieval: {
            max_relevance: 0.81,
            chunks_retrieved: 1,
            supporting_chunks: 1,
            retrieval_latency_ms: 4,
            embedding_latency_ms: 1,
            llm_latency_ms: 12,
            min_relevance_threshold: 0.5,
          },
        },
      ],
    });

    render(
      <MemoryRouter>
        <AssistantPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/Full-time employees receive 20 days of PTO/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/^Assistant$/)).toBeInTheDocument();
    expect(screen.queryByText(/Max relevance/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Grounded in 1 source/i)).toBeInTheDocument();
    expect(screen.getByText(/PTO Policy/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Show retrieval details/i })).toBeInTheDocument();
    expect(screen.queryByText(/chunk_id/i)).not.toBeInTheDocument();
  });

  it("renders insufficient-context without citation cards", async () => {
    listConversations.mockResolvedValue({
      items: [
        {
          id: "conv-2",
          title: "Parking",
          created_at: "2026-07-20T12:00:00Z",
          updated_at: "2026-07-20T12:00:00Z",
        },
      ],
      total: 1,
    });
    getConversation.mockResolvedValue({
      id: "conv-2",
      title: "Parking",
      created_at: "2026-07-20T12:00:00Z",
      updated_at: "2026-07-20T12:00:00Z",
      messages: [
        {
          id: "m3",
          role: "assistant",
          content:
            "I couldn't find enough information in the indexed documents to answer that question.",
          retrieval_top_k: 5,
          retrieval_min_score: 0.5,
          max_retrieval_score: 0.22,
          grounded: false,
          insufficient_context: true,
          answer_status: "insufficient_context",
          llm_latency_ms: 0,
          llm_model: "fake-llm",
          created_at: "2026-07-20T12:00:01Z",
          citations: [],
        },
      ],
    });

    render(
      <MemoryRouter>
        <AssistantPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/couldn't find enough information/i)).toBeInTheDocument();
    expect(screen.getByText(/Insufficient context in indexed documents/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Sources$/i)).not.toBeInTheDocument();
  });
});
