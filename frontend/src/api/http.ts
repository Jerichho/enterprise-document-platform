import type { ApiErrorBody } from "../types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const TOKEN_KEY = "ekp_access_token";
export const AUTH_CLEARED_EVENT = "ekp:auth-cleared";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

/** Clear the stored JWT and notify AuthProvider listeners. */
export function clearSession(): void {
  setStoredToken(null);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(AUTH_CLEARED_EVENT));
  }
}

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type RequestOptions = {
  method?: string;
  token?: string | null;
  body?: BodyInit | null;
  headers?: Record<string, string>;
  acceptStatuses?: number[];
  json?: unknown;
};

function shouldClearSessionOnUnauthorized(path: string, hadToken: boolean): boolean {
  if (!hadToken) return false;
  if (path.startsWith("/api/v1/auth/login") || path.startsWith("/api/v1/auth/register")) {
    return false;
  }
  return true;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers ?? {}) };
  const token = options.token === undefined ? getStoredToken() : options.token;
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let body = options.body ?? null;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body,
  });

  const accepted = options.acceptStatuses ?? [];
  if (!response.ok && !accepted.includes(response.status)) {
    let message = `Request failed (${response.status})`;
    let code: string | undefined;
    try {
      const payload = (await response.json()) as ApiErrorBody;
      message = payload.detail || message;
      code = payload.code;
    } catch {
      // ignore non-JSON error bodies
    }
    if (response.status === 401 && shouldClearSessionOnUnauthorized(path, Boolean(token))) {
      clearSession();
    }
    throw new ApiError(message, response.status, code);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
