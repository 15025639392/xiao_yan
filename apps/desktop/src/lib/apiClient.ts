const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

function normalizeBaseUrl(value: string | undefined | null): string | null {
  if (!value) {
    return null;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  return trimmed.replace(/\/+$/, "");
}

export function resolveApiBaseUrl(
  configuredBaseUrl: string | undefined | null = import.meta.env.VITE_API_BASE_URL,
): string {
  return normalizeBaseUrl(configuredBaseUrl) ?? DEFAULT_BASE_URL;
}

export const BASE_URL = resolveApiBaseUrl();

export async function buildHttpError(response: Response): Promise<Error> {
  let detail = "";
  try {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = await response.json();
      if (typeof payload?.detail === "string") {
        detail = payload.detail;
      } else if (payload && typeof payload === "object") {
        detail = JSON.stringify(payload);
      }
    } else {
      const text = (await response.text()).trim();
      if (text) {
        detail = text;
      }
    }
  } catch {
    detail = "";
  }

  if (detail) {
    return new Error(`request failed: ${response.status} (${detail})`);
  }
  return new Error(`request failed: ${response.status}`);
}

export function isRequestStatusError(error: unknown, status: number): boolean {
  return error instanceof Error && error.message.startsWith(`request failed: ${status}`);
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw await buildHttpError(response);
  }

  return response.json();
}

export async function put<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw await buildHttpError(response);
  }

  return response.json();
}

export async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);

  if (!response.ok) {
    throw await buildHttpError(response);
  }

  return response.json();
}

export async function del<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, { method: "DELETE" });
  if (!response.ok) {
    throw await buildHttpError(response);
  }
  return response.json();
}
