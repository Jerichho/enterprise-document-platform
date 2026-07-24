import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorBanner } from "./ErrorBanner";

describe("ErrorBanner", () => {
  it("renders message and optional retry action", () => {
    const onRetry = vi.fn();
    render(<ErrorBanner message="Something failed" onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Something failed");
    screen.getByRole("button", { name: /retry/i }).click();
    expect(onRetry).toHaveBeenCalled();
  });
});
