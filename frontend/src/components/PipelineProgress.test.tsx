import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PipelineProgress } from "./PipelineProgress";

describe("PipelineProgress", () => {
  it("marks earlier stages done and current stage active", () => {
    render(<PipelineProgress stage="embedding" />);
    expect(screen.getByText("Generating embeddings").closest("li")).toHaveClass("current");
    expect(screen.getByText("Uploaded").closest("li")).toHaveClass("done");
    expect(screen.getByText("Indexing").closest("li")).toHaveClass("todo");
  });

  it("shows failed state", () => {
    render(<PipelineProgress stage="failed" />);
    expect(screen.getByText(/ingestion failed/i)).toBeInTheDocument();
  });
});
