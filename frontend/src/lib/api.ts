// Base URL of the backend API. Set VITE_API_URL in frontend/.env for local/dev/prod.
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:4000";

// Thrown for any non-2xx response. Carries the parsed JSON error body (if any)
// so callers can pull out structured details like per-field validation errors
// (see backend/src/schemas/story.ts) without re-parsing the response.
export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

// Minimal fetch wrapper so every call gets a consistent base URL and JSON handling.
// Individual feature modules (stories, pages, auth) will build on top of this
// as those endpoints are added in later steps.
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      body.error ?? `Request failed with status ${res.status}`,
      res.status,
      body
    );
  }

  return res.json() as Promise<T>;
}

export { API_URL };
