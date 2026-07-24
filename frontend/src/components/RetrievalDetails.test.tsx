import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { RetrievalDetails } from "./RetrievalDetails";
import type { ChatMessage } from "../types";

const message: ChatMessage = {
  id: "msg-1",
  role: "assistant",
  content: "Employees receive twenty days of PTO.",
  retrieval_top_k: 5,
  retrieval_min_score: 0.35,
  max_retrieval_score: 0.81,
  grounded: true,
  insufficient_context: false,
  llm_latency_ms: 120,
  llm_model: "fake",
  created_at: "2026-07-20T12:00:00Z",
  citations: [
    {
      id: "cite-1",
      chunk_id: "chunk-1",
      document_id: "doc-1",
      document_title: "PTO Policy",
      page_number: 1,
      chunk_index: 0,
      relevance_score: 0.81,
      rank: 1,
      snippet: "twenty days of paid time off",
    },
  ],
};

describe("RetrievalDetails", () => {
  it("is collapsed by default and expands chunk scores", async () => {
    const user = userEvent.setup();
    render(<RetrievalDetails message={message} />);

    expect(screen.queryByText(/Max retrieval relevance/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /show retrieval details/i }));

    expect(screen.getByText("Maximum relevance")).toBeInTheDocument();
    expect(screen.getAllByText("0.810").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/relevance 0.810/i)).toBeInTheDocument();
    expect(screen.getByText(/twenty days of paid time off/i)).toBeInTheDocument();
    expect(screen.getByText(/chunk_id chunk-1/i)).toBeInTheDocument();
  });
});
