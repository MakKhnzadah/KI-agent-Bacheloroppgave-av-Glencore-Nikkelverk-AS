type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
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
  const base = (raw || "http://127.0.0.1:8000").trim();
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

export const apiClient = {
  baseUrl: getApiBaseUrl(),

  async getJson<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${getApiBaseUrl()}${path}`, {
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

  async postJson<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    const res = await fetch(`${getApiBaseUrl()}${path}`, {
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

  async patchJson<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    const res = await fetch(`${getApiBaseUrl()}${path}`, {
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

  async postForm<T>(path: string, form: FormData, init?: RequestInit): Promise<T> {
    const res = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      method: "POST",
      body: form,
    });

    await throwIfNotOk(res);
    return (await res.json()) as T;
  },

  async delete(path: string, init?: RequestInit): Promise<void> {
    const res = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      method: "DELETE",
      headers: {
        ...(init?.headers || {}),
      },
    });

    await throwIfNotOk(res);
  },
};
