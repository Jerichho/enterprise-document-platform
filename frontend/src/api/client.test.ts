import { describe, expect, it } from "vitest";

import { API_BASE_URL } from "./client";

describe("api client", () => {
  it("exposes a default API base URL", () => {
    expect(typeof API_BASE_URL).toBe("string");
    expect(API_BASE_URL.length).toBeGreaterThan(0);
  });
});
