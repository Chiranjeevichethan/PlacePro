// ============================================================
// PLACEPRO - PHASE 18 - API CLIENT
// ============================================================
// Thin fetch wrapper used by every service module. The backend URL
// comes from the VITE_API_URL environment variable - it is NEVER
// hard-coded in components.
// ============================================================

import { ApiError } from "../types";

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, "") ??
  "http://127.0.0.1:8000";

async function parseError(response: Response): Promise<ApiError> {
  let detail: string | undefined;
  let validation: ApiError["validation"];
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body?.detail)) {
      const items = body.detail as Array<{ loc: string[]; msg: string; type: string }>;
      validation = items;
      detail = items.map((d) => d.msg).join("; ");
    }
  } catch {
    // non-JSON error body - fall through with status text
  }
  return new ApiError(response.status, detail ?? response.statusText, validation);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: init?.body instanceof FormData
        ? init?.headers
        : { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch (err) {
    throw new ApiError(
      0,
      `Cannot reach the PlacePro API at ${API_BASE_URL}. Is the backend running?`,
    );
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "GET" });
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

export function apiUpload<T>(
  path: string,
  file: File,
  fieldName = "file",
): Promise<T> {
  const form = new FormData();
  form.append(fieldName, file);
  return apiFetch<T>(path, { method: "POST", body: form });
}
