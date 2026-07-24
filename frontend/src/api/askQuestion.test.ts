import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("./http", () => ({
  API_BASE_URL: "http://localhost:8000",
  apiRequest: vi.fn(),
}));

import { apiRequest } from "./http";
import { askQuestion } from "./client";

describe("askQuestion", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
    vi.mocked(apiRequest).mockResolvedValue({
      user_message: { id: "u1" },
      assistant_message: { id: "a1" },
    } as never);
  });

  it("sends department, category, and document filters", async () => {
    await askQuestion("conv-1", "How many PTO days?", {
      department: "HR",
      category: "Benefits",
      document_id: "doc-1",
    });

    expect(apiRequest).toHaveBeenCalledWith("/api/v1/conversations/conv-1/messages", {
      method: "POST",
      json: {
        content: "How many PTO days?",
        department: "HR",
        category: "Benefits",
        document_id: "doc-1",
      },
    });
  });
});
