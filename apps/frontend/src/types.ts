export type ConnectionState = "connecting" | "connected" | "reconnecting" | "disconnected" | "error";
export type AvailabilityState = "available" | "missing" | "stale" | "unsupported";

export interface UserSummary {
  id?: string;
  email?: string;
  display_name?: string;
}

export interface LoginResponse {
  user?: UserSummary;
  message?: string;
}

export interface FeatureAvailability {
  name: string;
  state: AvailabilityState;
  unit?: string | null;
  reason?: string | null;
}

export interface TelemetrySnapshot {
  captured_at?: string | null;
  phone_status?: string | null;
  obs_status?: string | null;
  mediamtx_status?: string | null;
  bitrate_kbps?: number | null;
  fps?: number | null;
  dropped_frames?: number | null;
  packet_loss_percent?: number | null;
  latency_ms?: number | null;
  jitter_ms?: number | null;
  upload_mbps?: number | null;
  download_mbps?: number | null;
  connection_capacity_mbps?: number | null;
  current_profile?: string | null;
  features?: FeatureAvailability[];
}

export interface AgentDecision {
  action?: "maintain" | "increase" | "reduce" | "switch_to_backup" | "maintain_backup" | "restore_live" | string;
  current_profile?: string | null;
  target_profile?: string | null;
  backup_active?: boolean;
  reason?: string | null;
  apply_profile?: boolean;
  apply_backup?: boolean;
  updated_at?: string | null;
}

export interface PredictionSnapshot {
  status?: "available" | "blocked" | "pending" | string;
  model_role?: "reactive" | "predictive" | string;
  model_version?: string | null;
  degradation_probability?: number | null;
  probability_downgrade_needed?: number | null;
  recommendation?: string | null;
  reason?: string | null;
  created_at?: string | null;
  features?: FeatureAvailability[];
}

export interface VideoEndpoints {
  whep_url?: string | null;
  webrtc_url?: string | null;
  hls_url?: string | null;
  whip_publish_url?: string | null;
  rtmp_publish_url?: string | null;
  tokens_expire_seconds?: number | null;
}

export interface VdoNinjaSession {
  phone_url?: string | null;
  embed_url?: string | null;
  expires_at?: string | null;
}

export interface StreamSession {
  id: string;
  name?: string | null;
  status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  telemetry?: TelemetrySnapshot | null;
  latest_prediction?: PredictionSnapshot | null;
  agent_decision?: AgentDecision | null;
  stream?: VideoEndpoints | null;
  vdo_ninja?: VdoNinjaSession | null;
}

export interface SessionListResponse {
  items: StreamSession[];
  total?: number;
}

export interface CreateSessionResponse {
  session?: StreamSession;
  id?: string;
  name?: string | null;
  status?: string | null;
  created_at?: string | null;
  vdo_ninja?: VdoNinjaSession | null;
  stream?: VideoEndpoints | null;
}

export interface ModelSummary {
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

export interface ModelsResponse {
  items?: ModelSummary[];
  models?: ModelSummary[];
  reactive?: ModelSummary;
  predictive?: ModelSummary;
}

export interface PairingCodeResponse {
  code: string;
  expires_at?: string | null;
}

export interface SessionSocketMessage {
  type?: string;
  session_id?: string;
  telemetry?: TelemetrySnapshot;
  prediction?: PredictionSnapshot;
  agent_decision?: AgentDecision;
  stream?: VideoEndpoints;
  session?: StreamSession;
}
