import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { CitationList } from "./CitationList";
import type { Citation } from "../types";

const citation: Citation = {
  id: "cite-1",
  chunk_id: "chunk-1",
  document_id: "doc-1",
  document_title: "PTO Policy",
  page_number: 1,
  chunk_index: 0,
  relevance_score: 0.812,
  rank: 1,
  snippet: "Employees receive twenty days of paid time off.",
};

describe("CitationList", () => {
  it("renders retrieval relevance and document link", () => {
    render(
      <MemoryRouter>
        <CitationList citations={[citation]} />
      </MemoryRouter>,
    );

    expect(screen.getByText(/PTO Policy/)).toBeInTheDocument();
    expect(screen.getByText(/Retrieval relevance: 0.81/)).toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/chunk_id/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open document/i })).toHaveAttribute(
      "href",
      "/documents/doc-1",
    );
  });

  it("invokes onSelect when a citation card is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <MemoryRouter>
        <CitationList citations={[citation]} onSelect={onSelect} />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: /PTO Policy/i }));
    expect(onSelect).toHaveBeenCalledWith(citation);
  });
});
