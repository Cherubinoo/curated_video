/**
 * Server-only helper for talking to the FastAPI backend. This file must
 * never be imported from a "use client" component - it reads the admin API
 * key from a non-NEXT_PUBLIC_ env var, which only exists server-side, so
 * the key never reaches the browser bundle. Server Components, Server
 * Actions, and Route Handlers all run on the server and may import it.
 */

const BACKEND_INTERNAL_URL = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
const API_KEY = process.env.API_KEY || "";

export class BackendError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`Backend request failed (${status}): ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_INTERNAL_URL}/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // ignore - use statusText
    }
    throw new BackendError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const backend = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
