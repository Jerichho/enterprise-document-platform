import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { JobStatusBadge, StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("shows fine-grained stage while processing", () => {
    render(<StatusBadge status="processing" stage="chunking" />);
    expect(screen.getByText("Chunking")).toBeInTheDocument();
  });

  it("shows completed label for finished documents", () => {
    render(<StatusBadge status="completed" stage="completed" />);
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });
});

describe("JobStatusBadge", () => {
  it("maps job statuses to badge tones", () => {
    const { rerender } = render(<JobStatusBadge status="failed" />);
    expect(screen.getByText("failed").className).toContain("danger");
    rerender(<JobStatusBadge status="completed" />);
    expect(screen.getByText("completed").className).toContain("ok");
  });
});
