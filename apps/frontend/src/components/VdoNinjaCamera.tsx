import { useEffect, useMemo, useRef, useState } from "react";
import type { VdoNinjaMetrics } from "../types";
import { isVdoStatsMessage, VdoStatsAccumulator } from "../lib/vdoStats";

interface VdoNinjaCameraProps {
  embedUrl?: string | null;
  onStatus?: (status: string) => void;
  onTelemetry?: (metrics: VdoNinjaMetrics, status: "waiting" | "connected" | "disconnected" | "error") => void;
  onLoad?: () => void;
}

function configuredOrigins(): Set<string> {
  const raw = import.meta.env.VITE_VDO_NINJA_ORIGINS || "https://vdo.ninja";
  return new Set(raw.split(",").map((value) => value.trim()).filter(Boolean));
}

/* Placeholder icon for camera unavailable */
const CameraPlaceholderIcon = () => (
  <svg className="size-12 text-media-muted" width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    {/* Phone outline */}
    <rect x="14" y="4" width="20" height="36" rx="3" />
    {/* Screen */}
    <rect x="16" y="8" width="16" height="24" rx="1" opacity="0.3" />
    {/* Camera dot */}
    <circle cx="24" cy="6" r="1" fill="currentColor" stroke="none" opacity="0.5" />
    {/* Signal arcs */}
    <path d="M36 14 Q40 12 42 14" opacity="0.3" />
    <path d="M38 11 Q42 9 45 11" opacity="0.2" />
    {/* Home button */}
    <circle cx="24" cy="38" r="2" opacity="0.3" />
  </svg>
);

export default function VdoNinjaCamera({ embedUrl, onStatus, onTelemetry, onLoad }: VdoNinjaCameraProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const statsRef = useRef(new VdoStatsAccumulator());
  const lastStatsAtRef = useRef<number | null>(null);
  const everConnectedRef = useRef(false);
  const disconnectedReportedRef = useRef(false);
  const [lastEvent, setLastEvent] = useState<string | null>(null);
  const [frameLoaded, setFrameLoaded] = useState(false);
  const origins = useMemo(configuredOrigins, []);
  const safeUrl = useMemo(() => {
    if (!embedUrl) return null;
    try {
      const parsed = new URL(embedUrl);
      if (!parsed.searchParams.has("autostart")) {
        parsed.searchParams.set("autostart", "1");
      }
      return origins.has(parsed.origin) ? parsed.toString() : null;
    } catch {
      return null;
    }
  }, [embedUrl, origins]);

  useEffect(() => {
    setFrameLoaded(false);
    statsRef.current = new VdoStatsAccumulator();
    lastStatsAtRef.current = null;
    everConnectedRef.current = false;
    disconnectedReportedRef.current = false;
  }, [safeUrl]);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (!origins.has(event.origin) || event.source !== iframeRef.current?.contentWindow) return;
      if (!event.data || typeof event.data !== "object") return;
      const data = event.data as Record<string, unknown>;
      if (isVdoStatsMessage(data)) {
        const statsKind = `${String(data.action ?? "")} ${String(data.type ?? "")} ${String(data.cib ?? "")}`.toLowerCase();
        const metrics = statsRef.current.read(
          data.stats ?? data.value ?? data,
          Date.now(),
          { allowOutgoingCapacity: statsKind.includes("remote") },
        );
        if (metrics) {
          lastStatsAtRef.current = Date.now();
          everConnectedRef.current = true;
          disconnectedReportedRef.current = false;
          setLastEvent("WebRTC activo");
          onStatus?.("connected");
          onTelemetry?.(metrics, "connected");
        }
        return;
      }
      const eventType = typeof data.type === "string" ? data.type : typeof data.action === "string" ? data.action : null;
      if (!eventType) return;
      const allowedEvents = new Set([
        "connected", "disconnected", "video-state", "stream-state", "view-connection",
        "push-connection", "guest-connected",
      ]);
      if (!allowedEvents.has(eventType)) return;
      const explicit = typeof data.status === "string" ? data.status.toLowerCase() : null;
      const disconnected = data.value === false || explicit === "disconnected" || ["disconnected", "error"].includes(eventType);
      const connected = data.value === true || explicit === "connected" || ["connected", "guest-connected"].includes(eventType);
      const status = disconnected ? "disconnected" : connected ? "connected" : explicit ?? "waiting";
      if (status === "connected") {
        everConnectedRef.current = true;
        disconnectedReportedRef.current = false;
      }
      setLastEvent(status);
      onStatus?.(status);
      if (status === "connected" || status === "disconnected" || status === "error") {
        onTelemetry?.({}, status);
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [onStatus, onTelemetry, origins]);

  useEffect(() => {
    if (!frameLoaded || !safeUrl) return;
    const targetOrigin = new URL(safeUrl).origin;
    const send = (message: Record<string, unknown>) => {
      iframeRef.current?.contentWindow?.postMessage(message, targetOrigin);
    };
    // Use one statistics source. Mixing continuous, fresh and remote replies
    // makes independent counter snapshots race and produces false zero/spike
    // bitrates. The received WebRTC video counters are the phone path that
    // StreamML needs to monitor.
    send({ getFreshStats: true, cib: "streamml-stats-fresh" });
    const polling = window.setInterval(() => {
      send({ getFreshStats: true, cib: "streamml-stats-fresh" });
    }, 2_000);
    const watchdog = window.setInterval(() => {
      const lastStatsAt = lastStatsAtRef.current;
      if (
        everConnectedRef.current && lastStatsAt != null
        && Date.now() - lastStatsAt > 8_000 && !disconnectedReportedRef.current
      ) {
        disconnectedReportedRef.current = true;
        setLastEvent("Sin señal");
        onStatus?.("disconnected");
        onTelemetry?.({}, "disconnected");
      }
    }, 2_000);
    return () => {
      window.clearInterval(polling);
      window.clearInterval(watchdog);
    };
  }, [frameLoaded, onStatus, onTelemetry, safeUrl]);

  if (!safeUrl) {
    return (
      <div className="flex min-h-64 w-full flex-col items-center justify-center gap-2 rounded-xl bg-media-background p-6 text-center text-media-muted">
        <CameraPlaceholderIcon />
        <strong className="mt-2 text-media-foreground">Vista del teléfono no disponible</strong>
        <span className="max-w-sm text-sm text-media-muted">La sesión VDO.Ninja no proporcionó una URL compatible.</span>
      </div>
    );
  }

  return (
    <div className="vdo-frame relative flex min-h-64 h-full w-full items-center justify-center overflow-hidden bg-media-background">
      <div className="hud-overlay absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="hud-corner hud-corner--tl" />
        <div className="hud-corner hud-corner--tr" />
        <div className="hud-corner hud-corner--bl" />
        <div className="hud-corner hud-corner--br" />
      </div>
      <iframe
        ref={iframeRef}
        src={safeUrl}
        className="w-full h-full border-0 absolute inset-0"
        title="Vista de cámara VDO.Ninja"
        allow="camera; microphone; autoplay; fullscreen; display-capture"
        referrerPolicy="no-referrer"
        onLoad={() => {
          setFrameLoaded(true);
          setLastEvent("Esperando señal");
          onStatus?.("waiting");
          onTelemetry?.({}, "waiting");
          onLoad?.();
        }}
      />
      <span className="media-mode absolute bottom-3 right-3 rounded-lg bg-overlay px-2.5 py-1.5 text-[11px] font-medium text-media-foreground/80 backdrop-blur">VDO.Ninja · {lastEvent ?? "Esperando evento"}</span>
    </div>
  );
}
