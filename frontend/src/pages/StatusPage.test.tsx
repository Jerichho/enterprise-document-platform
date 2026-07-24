import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { StatusPage } from "./StatusPage";

vi.mock("../api/client", () => ({
  fetchHealth: vi.fn().mockResolvedValue({
    status: "ok",
    service: "Enterprise Knowledge Management Platform",
    version: "0.1.0",
    environment: "test",
  }),
  fetchReady: vi.fn().mockResolvedValue({
    status: "ready",
    environment: "test",
    version: "0.1.0",
    checks: [
      { name: "database", status: "ok", detail: null },
      { name: "pgvector", status: "ok", detail: "vector extension installed" },
      { name: "storage", status: "ok", detail: "writable" },
      { name: "llm_provider", status: "ok", detail: "fake" },
      { name: "embedding_provider", status: "ok", detail: "fake" },
    ],
  }),
}));

describe("StatusPage", () => {
  it("renders health environment and dependency checks", async () => {
    render(
      <MemoryRouter>
        <StatusPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("test")).toBeInTheDocument();
    });
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText("pgvector extension")).toBeInTheDocument();
    expect(screen.getAllByText("ready").length).toBeGreaterThan(0);
  });
});
