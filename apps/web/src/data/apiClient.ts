// Thin fetch wrapper around the FastAPI backend.
// Every page-facing function in mockApi.ts goes through this — it's the
// only place that knows about HTTP, base URLs, or error shapes.
//
// Auth: if a JWT is stored in localStorage (under ``unilead_token``), it's
// automatically attached to every request via the Authorization header.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'https://localhost:8000/api';

const TOKEN_KEY = 'unilead_token';

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function buildHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...((extra as Record<string, string>) ?? {}),
  };
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : detail;
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: 'GET',
      headers: buildHeaders(),
    });
  } catch {
    throw new Error('Could not reach the server. Is the backend running?');
  }
  return handleResponse<T>(res);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: buildHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error('Could not reach the server. Is the backend running?');
  }
  return handleResponse<T>(res);
}
