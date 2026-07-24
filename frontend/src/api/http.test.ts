import { afterEach, describe, expect, it, vi } from "vitest";

import { AUTH_CLEARED_EVENT, clearSession, getStoredToken, setStoredToken } from "./http";

describe("session helpers", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("stores and clears tokens", () => {
    setStoredToken("abc");
    expect(getStoredToken()).toBe("abc");
    clearSession();
    expect(getStoredToken()).toBeNull();
  });

  it("emits auth-cleared when the session is cleared", () => {
    const handler = vi.fn();
    window.addEventListener(AUTH_CLEARED_EVENT, handler);
    clearSession();
    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener(AUTH_CLEARED_EVENT, handler);
  });
});
