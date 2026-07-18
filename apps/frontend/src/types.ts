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
  stream_active?: boolean | null;
  stream_reconnecting?: boolean | null;
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
  reason_code?: string | null;
  operational_state?: "stable" | "observing" | "protecting" | "degraded" | "backup" | "recovering" | string;
  apply_profile?: boolean;
  apply_backup?: boolean;
  updated_at?: string | null;
}

export interface PredictionSnapshot {
  status?: "available" | "executed" | "blocked" | "pending" | string;
  model_role?: "reactive" | "predictive" | string;
  model_version?: string | null;
  degradation_probability?: number | null;
  probability_downgrade_needed?: number | null;
  recommendation?: string | null;
  reason?: string | null;
  evidence?: Record<string, string | number | boolean | null> | null;
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
  source?: "streamml" | "external" | string;
}

export interface SessionConfiguration {
  platform?: "youtube" | "twitch" | "facebook" | "kick" | "custom" | string | null;
  resolution?: "480p" | "720p" | "1080p" | string | null;
  planned_duration_hours?: "1" | "2" | "4" | "8" | string | null;
  connection_type?: "cable" | "wifi" | "mobile" | string | null;
  vdo_embed_url?: string | null;
}

export interface StreamSession {
  id: string;
  name?: string | null;
  status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  telemetry?: TelemetrySnapshot | null;
  latest_prediction?: PredictionSnapshot | null;
  recent_predictions?: PredictionSnapshot[];
  agent_decision?: AgentDecision | null;
  stream?: VideoEndpoints | null;
  vdo_ninja?: VdoNinjaSession | null;
  configuration?: SessionConfiguration | null;
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
  official_release?: boolean;
  trained_at?: string | null;
  split_method?: string | null;
  split_counts?: Record<string, number> | null;
  dataset?: Record<string, unknown> | null;
  validation?: ModelMetricSummary | null;
  test?: ModelMetricSummary | null;
  baseline?: { model?: string; test?: ModelMetricSummary | null } | null;
  generalization_gap?: number | null;
  improvement_over_baseline_macro_f1?: number | null;
  model_comparison?: Record<string, ModelComparisonSummary> | null;
  feature_importance?: Array<{ feature: string; importance: number }> | null;
  limitations?: string[];
  lookback_seconds?: number | null;
  future_horizon_seconds?: number | null;
}

export interface ModelMetricSummary {
  accuracy?: number | null;
  balanced_accuracy?: number | null;
  macro_f1?: number | null;
  precision_by_class?: Record<string, number>;
  recall_by_class?: Record<string, number>;
  f1_by_class?: Record<string, number>;
  support_by_class?: Record<string, number>;
  confusion_matrix?: number[][];
  pr_auc?: number | null;
  roc_auc?: number | null;
}

export interface ModelComparisonSummary {
  best_parameters?: Record<string, unknown> | null;
  train_groupkfold_macro_f1?: number | null;
  validation?: Pick<ModelMetricSummary, "accuracy" | "balanced_accuracy" | "macro_f1">;
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
  session_id?: string;
}

export interface PreferencesSettings {
  language: "es";
  timezone: "auto" | "America/Guayaquil" | "UTC";
  dark_mode: boolean;
  alert_detail: "low" | "normal" | "high";
}

export interface StreamSettings {
  preferred_resolution: "480p" | "720p" | "1080p";
  preferred_profile: "low" | "medium" | "high";
  platform: "youtube" | "twitch" | "facebook" | "kick" | "custom";
  live_scene: string;
  backup_scene: string;
  network_probe_interval_seconds: number;
  network_probe_bytes: number;
}

export interface ConnectorStatus {
  id: string;
  session_id: string;
  name: string;
  version: string;
  last_seen_at?: string | null;
  connected: boolean;
}

export interface SettingsResponse {
  user: UserSummary;
  preferences: PreferencesSettings;
  stream: StreamSettings;
  connectors: ConnectorStatus[];
  updated_at?: string;
  security?: { server_secrets_managed_externally?: boolean; message?: string };
}

export interface SessionSocketMessage {
  type?: string;
  session_id?: string;
  telemetry?: TelemetrySnapshot;
  prediction?: PredictionSnapshot;
  predictions?: PredictionSnapshot[];
  agent_decision?: AgentDecision;
  stream?: VideoEndpoints;
  session?: StreamSession;
}
