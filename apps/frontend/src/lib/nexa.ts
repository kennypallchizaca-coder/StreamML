import type { AgentDecision, PredictionSnapshot, TelemetrySnapshot } from "../types";

export type NexaMood =
  | "waiting"
  | "observing"
  | "stable"
  | "protecting"
  | "backup"
  | "recovering"
  | "attention";

export type NexaVisualState = "neutral" | "thinking" | "working" | "success" | "error";

const VISUAL_STATE_BY_MOOD: Record<NexaMood, NexaVisualState> = {
  waiting: "neutral",
  observing: "thinking",
  stable: "success",
  protecting: "working",
  backup: "working",
  recovering: "thinking",
  attention: "error",
};

export function getNexaVisualState(mood: NexaMood): NexaVisualState {
  return VISUAL_STATE_BY_MOOD[mood];
}

export interface NexaState {
  mood: NexaMood;
  label: string;
  message: string;
}

interface NexaStateInput {
  telemetry?: TelemetrySnapshot | null;
  decision?: AgentDecision | null;
  predictivePrediction?: PredictionSnapshot | null;
}

const HEALTHY_OBS_STATES = new Set(["connected", "online", "active", "streaming"]);

/**
 * Traduce el estado operativo real a la personalidad visual de Nexa.
 * No crea decisiones: solo explica telemetría, predicciones y acciones existentes.
 */
export function getNexaState({
  telemetry,
  decision,
  predictivePrediction,
}: NexaStateInput): NexaState {
  const action = decision?.action?.toLowerCase();
  const recommendation = predictivePrediction?.recommendation?.toLowerCase();
  const obsStatus = telemetry?.obs_status?.toLowerCase();

  if (decision?.backup_active || action === "switch_to_backup" || action === "maintain_backup") {
    return {
      mood: "backup",
      label: "Protegiendo la emisión",
      message: "La señal de respaldo está activa mientras verifico que el vivo vuelva a ser estable.",
    };
  }

  if (action === "restore_live") {
    return {
      mood: "recovering",
      label: "Restaurando el vivo",
      message: "La señal principal se recuperó y estoy confirmando que permanezca estable.",
    };
  }

  if (!telemetry) {
    return {
      mood: "waiting",
      label: "Esperando telemetría",
      message: "Vincula el conector para que pueda observar la señal y acompañar cada decisión.",
    };
  }

  if (telemetry.stream_reconnecting) {
    return {
      mood: "recovering",
      label: "Reconectando la señal",
      message: "OBS está recuperando la salida. Mantengo el sistema bajo observación.",
    };
  }

  if (obsStatus && !HEALTHY_OBS_STATES.has(obsStatus)) {
    return {
      mood: "attention",
      label: "Necesito tu atención",
      message: "No recibo una señal válida de OBS. Revisa la conexión del conector.",
    };
  }

  if (telemetry.stream_active === false) {
    return {
      mood: "attention",
      label: "OBS está listo",
      message: "La telemetría funciona, pero la salida de transmisión aún está detenida.",
    };
  }

  if (action === "reduce" || recommendation === "downgrade_needed") {
    return {
      mood: "protecting",
      label: "Anticipando degradación",
      message: "Detecté riesgo para el perfil actual y priorizo la continuidad de la transmisión.",
    };
  }

  if (predictivePrediction?.status === "blocked") {
    return {
      mood: "observing",
      label: "Construyendo contexto",
      message: "Estoy reuniendo el historial necesario para activar la predicción de los próximos minutos.",
    };
  }

  if (telemetry.stream_active && (action === "maintain" || action === "increase")) {
    return {
      mood: "stable",
      label: "Señal estable",
      message: "Los modelos y la política del agente están supervisando la calidad en tiempo real.",
    };
  }

  return {
    mood: "observing",
    label: "Analizando la señal",
    message: "Estoy observando la telemetría y esperando la siguiente decisión del agente.",
  };
}
