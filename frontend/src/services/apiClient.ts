import { authService } from "./authService";

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

type ApiClientRequestInit = RequestInit & {
  requireAuth?: boolean;
  retryOn401?: boolean;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly details?: Record<string, unknown>;

  constructor(message: string, status: number, code?: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function getApiBaseUrl(): string {
  const raw = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined;
  const base = (raw || "http://127.0.0.1:8001").trim();
  return base.replace(/\/+$/, "");
}

async function parseJsonSafely(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function throwIfNotOk(res: Response): Promise<void> {
  if (res.ok) return;

  const payload = (await parseJsonSafely(res)) as ApiErrorPayload | string | null;
  if (payload && typeof payload === "object" && "error" in payload) {
    const err = (payload as ApiErrorPayload).error;
    throw new ApiError(err?.message || `Request failed (${res.status})`, res.status, err?.code, err?.details);
  }

  throw new ApiError(
    typeof payload === "string" && payload ? payload : `Request failed (${res.status})`,
    res.status,
  );
}

function withBearerAuthorization(headers: HeadersInit | undefined, token: string): Headers {
  const merged = new Headers(headers || {});
  merged.set("Authorization", `Bearer ${token}`);
  return merged;
}

async function request(path: string, init?: ApiClientRequestInit): Promise<Response> {
  const { requireAuth = false, retryOn401 = requireAuth, ...requestInit } = init || {};
  const url = `${getApiBaseUrl()}${path}`;

  const token = requireAuth ? authService.getToken() : null;
  const initialHeaders = requireAuth && token
    ? withBearerAuthorization(requestInit.headers, token)
    : requestInit.headers;

  let response = await fetch(url, {
    ...requestInit,
    headers: initialHeaders,
  });

  if (response.status !== 401 || !requireAuth || !retryOn401) {
    return response;
  }

  try {
    const freshToken = await authService.refreshToken();
    response = await fetch(url, {
      ...requestInit,
      headers: withBearerAuthorization(requestInit.headers, freshToken),
    });
  } catch {
    return response;
  }

  return response;
}

export const apiClient = {
  baseUrl: getApiBaseUrl(),

  async getJson<T>(path: string, init?: ApiClientRequestInit): Promise<T> {
    const res = await request(path, {
      ...init,
      method: "GET",
      headers: {
        Accept: "application/json",
        ...(init?.headers || {}),
      },
    });

    await throwIfNotOk(res);
    return (await res.json()) as T;
  },

  async postJson<T>(path: string, body?: unknown, init?: ApiClientRequestInit): Promise<T> {
    const res = await request(path, {
      ...init,
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    await throwIfNotOk(res);
    return (await res.json()) as T;
  },

  async patchJson<T>(path: string, body?: unknown, init?: ApiClientRequestInit): Promise<T> {
    const res = await request(path, {
      ...init,
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    await throwIfNotOk(res);
    return (await res.json()) as T;
  },

  async postForm<T>(path: string, form: FormData, init?: ApiClientRequestInit): Promise<T> {
    const res = await request(path, {
      ...init,
      method: "POST",
      body: form,
    });

    await throwIfNotOk(res);
    return (await res.json()) as T;
  },

  async delete(path: string, init?: ApiClientRequestInit): Promise<void> {
    const res = await request(path, {
      ...init,
      method: "DELETE",
      headers: {
        ...(init?.headers || {}),
      },
    });

    await throwIfNotOk(res);
  },
};
