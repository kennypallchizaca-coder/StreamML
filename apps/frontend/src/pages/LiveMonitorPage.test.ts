import { describe, expect, it } from "vitest";

import {
  getGeneralState,
  latestPredictionByRole,
  liveBadge,
  translateRecommendation,
  translateRisk,
} from "./LiveMonitorPage";


describe("estado real de la transmisión", () => {
  it("no muestra EN VIVO cuando OBS está conectado pero la salida está detenida", () => {
    const telemetry = { obs_status: "connected", stream_active: false };
    expect(liveBadge(telemetry).label).toBe("OBS LISTO");
    expect(getGeneralState(telemetry).state.toLowerCase()).toContain("transmisión detenida");
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

  it("explica los resultados de los modelos con el lenguaje de los notebooks", () => {
    const reactive = translateRecommendation("medium");
    expect(reactive.title).toBe("Señal estable (Calidad Media · medium)");
    expect(reactive.summary).toBe("Las condiciones de red son regulares pero aceptables.");
    expect(reactive.cause).toBe("Se han detectado variaciones normales en tu velocidad de internet.");

    const predictive = translateRecommendation("downgrade_needed");
    expect(predictive.title).toBe("Riesgo de corte inminente (downgrade_needed)");
    expect(predictive.action).toBe("El sistema reducirá automáticamente la resolución para proteger la transmisión.");

    const risk = translateRisk(0.52);
    expect(risk.level).toBe("Incierta (Probabilidad media)");
    expect(risk.detail).toBe("Hay ciertas variaciones en los datos. Podría suceder, pero no es definitivo.");
  });

  it("distingue la probabilidad del clasificador reactivo de la decisión predictiva", () => {
    const reactive = {
      model_role: "reactive",
      recommendation: "medium" as const,
      probabilities: { low: 0.1, medium: 0.72, high: 0.18 },
    };

    expect(reactive.probabilities[reactive.recommendation]).toBe(0.72);
    expect(translateRecommendation(reactive.recommendation).title).toBe("Señal estable (Calidad Media · medium)");
  });
});
