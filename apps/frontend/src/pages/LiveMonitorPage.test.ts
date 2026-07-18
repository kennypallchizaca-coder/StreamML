import { describe, expect, it } from "vitest";

import { getGeneralState, latestPredictionByRole, liveBadge } from "./LiveMonitorPage";


describe("estado real de la transmisión", () => {
  it("no muestra EN VIVO cuando OBS está conectado pero la salida está detenida", () => {
    const telemetry = { obs_status: "connected", stream_active: false };
    expect(liveBadge(telemetry).label).toBe("OBS LISTO");
    expect(getGeneralState(telemetry).state).toContain("transmisión detenida");
  });

  it("muestra EN VIVO solo cuando OBS informa una salida activa", () => {
    expect(liveBadge({ obs_status: "connected", stream_active: true }).label).toBe("EN VIVO");
  });

  it("prioriza el estado de reconexión", () => {
    const telemetry = { obs_status: "reconnecting", stream_reconnecting: true };
    expect(liveBadge(telemetry).label).toBe("RECONECTANDO");
    expect(getGeneralState(telemetry).state).toContain("Reconectando");
  });

  it("separa los resultados reactivo y predictivo sin confundirlos con el agente", () => {
    const predictions = [
      { model_role: "predictive", recommendation: "maintain", created_at: "2026-07-17T12:00:02Z" },
      { model_role: "reactive", recommendation: "high", created_at: "2026-07-17T12:00:01Z" },
      { model_role: "predictive", recommendation: "downgrade_needed", created_at: "2026-07-17T11:59:00Z" },
    ];

    expect(latestPredictionByRole(predictions, "reactive")?.recommendation).toBe("high");
    expect(latestPredictionByRole(predictions, "predictive")?.recommendation).toBe("maintain");
  });
});
