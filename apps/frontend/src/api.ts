import type {
  CreateSessionResponse,
  LoginResponse,
  ModelsResponse,
  PairingCodeResponse,
  SessionListResponse,
  StreamSession,
  VideoEndpoints,
} from "./types";

const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim() || "/api/v1";
export const API_BASE_URL = configuredBase.replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object") {
    const value = payload as Record<string, unknown>;
    if (typeof value.detail === "string") return value.detail;
    if (typeof value.message === "string") return value.message;
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  const contentType = response.headers.get("content-type") ?? "";
  const payload: unknown = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new Event("streamml:unauthorized"));
    }
    throw new ApiError(errorMessage(payload, `Error HTTP ${response.status}`), response.status, payload);
  }

  return payload as T;
}

export const api = {
  login(email: string, password: string) {
    return request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  me() {
    return request<LoginResponse>("/auth/me");
  },
  logout() {
    return request<{ message?: string }>("/auth/logout", { method: "POST" });
  },
  listSessions() {
    return request<SessionListResponse | StreamSession[]>("/sessions");
  },
  createSession(name: string) {
    return request<CreateSessionResponse>("/sessions", {
      method: "POST",
      body: JSON.stringify({ name: name.trim() || undefined }),
    });
  },
  getSession(id: string) {
    return request<StreamSession>(`/sessions/${encodeURIComponent(id)}`);
  },
  getStream(id: string) {
    return request<VideoEndpoints>(`/streams/${encodeURIComponent(id)}`);
  },
  getModels() {
    return request<ModelsResponse | ModelSummary[]>("/models");
  },
  createPairingCode(sessionId: string) {
    return request<PairingCodeResponse>("/pairing/codes", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    });
  },
};

interface ModelSummary {
  role?: string;
  name?: string;
  algorithm?: string;
  version?: string;
  threshold?: number | null;
  features?: string[];
  classes?: string[];
  metrics?: Record<string, unknown>;
  status?: string;
}

export function normalizeSessions(value: SessionListResponse | StreamSession[]): StreamSession[] {
  return Array.isArray(value) ? value : value.items ?? [];
}
