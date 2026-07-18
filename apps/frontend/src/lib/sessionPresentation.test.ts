import { describe, expect, it } from "vitest";
import { isSessionLive, needsQualityAttention, sessionStateLabel } from "./sessionPresentation";

describe("presentación del estado real de sesiones", () => {
  it("solo considera en vivo los estados de emisión", () => {
    expect(isSessionLive("active")).toBe(true);
    expect(isSessionLive("ready")).toBe(false);
    expect(isSessionLive("offline")).toBe(false);
  });

  it("distingue una sesión sin señal de una finalizada", () => {
    expect(sessionStateLabel("offline")).toBe("Sin señal");
    expect(sessionStateLabel("completed")).toBe("Finalizada");
  });

  it("marca únicamente recomendaciones que requieren atención", () => {
    expect(needsQualityAttention("downgrade_needed")).toBe(true);
    expect(needsQualityAttention("low")).toBe(true);
    expect(needsQualityAttention("maintain")).toBe(false);
  });
});
