import { describe, expect, it } from "vitest";

import { getNexaState, getNexaVisualState } from "./nexa";

describe("personalidad operativa de Nexa", () => {
  it("reduce los estados técnicos a cinco poses visuales comprensibles", () => {
    expect(getNexaVisualState("waiting")).toBe("neutral");
    expect(getNexaVisualState("observing")).toBe("thinking");
    expect(getNexaVisualState("protecting")).toBe("working");
    expect(getNexaVisualState("stable")).toBe("success");
    expect(getNexaVisualState("attention")).toBe("error");
  });

  it("espera telemetría sin inventar un estado de transmisión", () => {
    expect(getNexaState({}).mood).toBe("waiting");
  });

  it("prioriza el respaldo sobre cualquier otra señal", () => {
    const state = getNexaState({
      telemetry: { obs_status: "connected", stream_active: true },
      decision: { action: "maintain_backup", backup_active: true },
      predictivePrediction: { recommendation: "maintain" },
    });
    expect(state.mood).toBe("backup");
    expect(state.label).toContain("Protegiendo");
  });

  it("comunica una reducción predictiva como protección anticipada", () => {
    const state = getNexaState({
      telemetry: { obs_status: "connected", stream_active: true },
      predictivePrediction: { status: "executed", recommendation: "downgrade_needed" },
    });
    expect(state.mood).toBe("protecting");
  });

  it("distingue una salida detenida de una emisión estable", () => {
    const stopped = getNexaState({ telemetry: { obs_status: "connected", stream_active: false } });
    const stable = getNexaState({
      telemetry: { obs_status: "connected", stream_active: true },
      decision: { action: "maintain" },
    });
    expect(stopped.mood).toBe("attention");
    expect(stable.mood).toBe("stable");
  });
});
