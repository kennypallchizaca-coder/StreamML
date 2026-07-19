import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import VdoNinjaCamera from "../components/VdoNinjaCamera";
import type { VdoNinjaMetrics } from "../types";

export default function VdoBridgePage() {
  const { sessionId } = useParams();
  const [searchParams] = useSearchParams();
  const bridgeToken = searchParams.get("token") ?? "";
  const [embedUrl, setEmbedUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reporterId = useRef(
    typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `obs-bridge-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  );
  const sequence = useRef(Date.now());

  useEffect(() => {
    if (!sessionId || !bridgeToken) {
      setError("El enlace monitorizado de OBS está incompleto.");
      return;
    }
    void api.getVdoNinjaBridge(sessionId, bridgeToken)
      .then((value) => setEmbedUrl(value.embed_url))
      .catch(() => setError("StreamML no pudo validar esta fuente monitorizada."));
  }, [bridgeToken, sessionId]);

  const report = useCallback((
    metrics: VdoNinjaMetrics,
    status: "waiting" | "connected" | "disconnected" | "error",
  ) => {
    if (!sessionId || !bridgeToken) return;
    void api.sendVdoNinjaTelemetry({
      session_id: sessionId,
      source: "vdo_ninja_iframe",
      reporter_id: reporterId.current,
      sequence: sequence.current++,
      observed_at: new Date().toISOString(),
      status,
      metrics,
    }, bridgeToken).catch(() => undefined);
  }, [bridgeToken, sessionId]);

  if (error) {
    return <main className="fixed inset-0 grid place-items-center bg-black p-8 text-center text-white">{error}</main>;
  }
  if (!embedUrl) {
    return <main className="fixed inset-0 grid place-items-center bg-black text-white">Conectando StreamML…</main>;
  }
  return (
    <main className="fixed inset-0 bg-black">
      <VdoNinjaCamera embedUrl={embedUrl} onTelemetry={report} />
    </main>
  );
}
