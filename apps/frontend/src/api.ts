import type {
  CreateSessionResponse,
  LoginResponse,
  ModelsResponse,
  PairingCodeResponse,
  PreferencesSettings,
  SessionListResponse,
  SettingsResponse,
  StreamSession,
  StreamSettings,
  VideoEndpoints,
  VdoNinjaTelemetryPayload,
} from "./types";

const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim() || "/api/v1";
const API_BASE_URL = configuredBase.replace(/\/$/, "");

class ApiError extends Error {
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

async function request<T>(
  path: string,
  init: RequestInit = {},
  options: { suppressUnauthorizedEvent?: boolean } = {},
): Promise<T> {
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
    if (response.status === 401 && !options.suppressUnauthorizedEvent) {
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
    return request<LoginResponse>("/auth/me", {}, { suppressUnauthorizedEvent: true });
  },
  logout() {
    return request<{ message?: string }>("/auth/logout", { method: "POST" });
  },
  listSessions() {
    return request<SessionListResponse | StreamSession[]>("/sessions");
  },
  createSession(
    name: string,
    options: {
      platform?: string;
      resolution?: string;
      planned_duration_hours?: string;
      connection_type?: string;
    } = {},
  ) {
    return request<CreateSessionResponse>("/sessions", {
      method: "POST",
      body: JSON.stringify({ name: name.trim() || undefined, ...options }),
    });
  },
  getSession(id: string) {
    return request<StreamSession>(`/sessions/${encodeURIComponent(id)}`);
  },
  getStream(id: string) {
    return request<VideoEndpoints>(`/streams/${encodeURIComponent(id)}`);
  },
  sendVdoNinjaTelemetry(payload: VdoNinjaTelemetryPayload, bridgeToken?: string) {
    return request<{ accepted: boolean; duplicate: boolean; phone_status?: string | null }>(
      "/telemetry/vdo-ninja",
      {
        method: "POST",
        body: JSON.stringify(payload),
        headers: bridgeToken ? { Authorization: `Bearer ${bridgeToken}` } : undefined,
      },
      { suppressUnauthorizedEvent: Boolean(bridgeToken) },
    );
  },
  getVdoNinjaBridge(sessionId: string, bridgeToken: string) {
    return request<{ session_id: string; embed_url: string }>(
      `/telemetry/vdo-ninja/${encodeURIComponent(sessionId)}/bridge`,
      { headers: { Authorization: `Bearer ${bridgeToken}` } },
      { suppressUnauthorizedEvent: true },
    );
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
  getSettings() {
    return request<SettingsResponse>("/settings");
  },
  updateAccount(payload: { display_name: string; current_password?: string; new_password?: string }) {
    return request<{ user: LoginResponse["user"] }>("/settings/account", {
      method: "PUT", body: JSON.stringify(payload),
    });
  },
  updatePreferences(payload: PreferencesSettings) {
    return request<{ preferences: PreferencesSettings; updated_at?: string }>("/settings/preferences", {
      method: "PUT", body: JSON.stringify(payload),
    });
  },
  updateStreamSettings(payload: StreamSettings) {
    return request<{ stream: StreamSettings; updated_at?: string }>("/settings/stream", {
      method: "PUT", body: JSON.stringify(payload),
    });
  },
  updateVideoLink(sessionId: string, embedUrl: string) {
    return request<{ session_id: string; embed_url: string }>(
      `/settings/sessions/${encodeURIComponent(sessionId)}/video-link`,
      { method: "PUT", body: JSON.stringify({ embed_url: embedUrl }) },
    );
  },
  exportData() {
    return request<Record<string, unknown>>("/settings/export");
  },
  deleteHistory() {
    return request<{ deleted_sessions: number }>("/settings/history", {
      method: "DELETE", body: JSON.stringify({ confirmation: "DELETE_HISTORY" }),
    });
  },
  deleteAccount(confirmation: string, currentPassword: string) {
    return request<void>("/settings/account", {
      method: "DELETE", body: JSON.stringify({ confirmation, current_password: currentPassword }),
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
