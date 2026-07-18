const liveSessionStates = new Set(["active", "live", "streaming"]);
const downgradeRecommendations = new Set(["low", "downgrade", "downgrade_needed"]);

export function isSessionLive(status?: string | null): boolean {
  return liveSessionStates.has(status?.trim().toLowerCase() ?? "");
}

export function sessionStateLabel(status?: string | null): string {
  switch (status?.trim().toLowerCase()) {
    case "active":
    case "live":
    case "streaming":
      return "En vivo";
    case "ready":
      return "OBS listo";
    case "offline":
      return "Sin señal";
    case "created":
      return "Sin vincular";
    case "completed":
      return "Finalizada";
    default:
      return "Estado no disponible";
  }
}

export function needsQualityAttention(recommendation?: string | null): boolean {
  return downgradeRecommendations.has(recommendation?.trim().toLowerCase() ?? "");
}
