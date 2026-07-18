import { useEffect, useMemo, useRef, useState } from "react";

interface VdoNinjaCameraProps {
  embedUrl?: string | null;
  onStatus?: (status: string) => void;
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

export default function VdoNinjaCamera({ embedUrl, onStatus, onLoad }: VdoNinjaCameraProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [lastEvent, setLastEvent] = useState<string | null>(null);
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
    const handler = (event: MessageEvent) => {
      if (!origins.has(event.origin) || event.source !== iframeRef.current?.contentWindow) return;
      if (!event.data || typeof event.data !== "object") return;
      const data = event.data as Record<string, unknown>;
      const eventType = typeof data.type === "string" ? data.type : typeof data.action === "string" ? data.action : null;
      if (!eventType) return;
      const allowedEvents = new Set(["connected", "disconnected", "video-state", "stream-state", "view-connection"]);
      if (!allowedEvents.has(eventType)) return;
      const status = typeof data.status === "string" ? data.status : eventType;
      setLastEvent(status);
      onStatus?.(status);
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [onStatus, origins]);

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
        onLoad={onLoad}
      />
      <span className="media-mode absolute bottom-3 right-3 rounded-lg bg-overlay px-2.5 py-1.5 text-[11px] font-medium text-media-foreground/80 backdrop-blur">VDO.Ninja · {lastEvent ?? "Esperando evento"}</span>
    </div>
  );
}
