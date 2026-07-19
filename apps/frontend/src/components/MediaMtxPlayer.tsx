import type HlsType from "hls.js";
import { useEffect, useRef, useState } from "react";
import { AlertCircle, VideoOff } from "@/components/icons";
import { Badge } from "./ui/badge";

interface MediaMtxPlayerProps {
  whepUrl?: string | null;
  hlsUrl?: string | null;
}

type PlaybackMode = "webrtc" | "hls" | "unavailable";

function waitForIceGathering(peer: RTCPeerConnection): Promise<void> {
  if (peer.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const timeout = window.setTimeout(done, 5000);
    function done() {
      window.clearTimeout(timeout);
      peer.removeEventListener("icegatheringstatechange", check);
      resolve();
    }
    function check() {
      if (peer.iceGatheringState === "complete") done();
    }
    peer.addEventListener("icegatheringstatechange", check);
  });
}

export default function MediaMtxPlayer({ whepUrl, hlsUrl }: MediaMtxPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [mode, setMode] = useState<PlaybackMode>(whepUrl ? "webrtc" : hlsUrl ? "hls" : "unavailable");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMode(whepUrl ? "webrtc" : hlsUrl ? "hls" : "unavailable");
    setError(null);
  }, [whepUrl, hlsUrl]);

  useEffect(() => {
    if (mode !== "webrtc" || !whepUrl || !videoRef.current) return;
    const controller = new AbortController();
    const peer = new RTCPeerConnection();
    const video = videoRef.current;
    let resourceUrl: string | null = null;

    peer.addTransceiver("video", { direction: "recvonly" });
    peer.addTransceiver("audio", { direction: "recvonly" });
    peer.ontrack = (event) => {
      video.srcObject = event.streams[0];
      video.play().catch((e) => console.warn("Autoplay prevenido por el navegador", e));
    };
    peer.onconnectionstatechange = () => {
      if (["failed", "disconnected", "closed"].includes(peer.connectionState) && hlsUrl) setMode("hls");
    };

    void (async () => {
      try {
        const offer = await peer.createOffer();
        await peer.setLocalDescription(offer);
        await waitForIceGathering(peer);
        const response = await fetch(whepUrl, {
          method: "POST",
          headers: { "Content-Type": "application/sdp", Accept: "application/sdp" },
          body: peer.localDescription?.sdp,
          credentials: "omit",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`WHEP respondió ${response.status}`);
        const location = response.headers.get("location");
        if (location) resourceUrl = new URL(location, whepUrl).toString();
        await peer.setRemoteDescription({ type: "answer", sdp: await response.text() });
      } catch (reason) {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "No fue posible iniciar WebRTC");
        setMode(hlsUrl ? "hls" : "unavailable");
      }
    })();

    return () => {
      controller.abort();
      peer.close();
      video.srcObject = null;
      if (resourceUrl) void fetch(resourceUrl, { method: "DELETE", credentials: "omit" }).catch(() => undefined);
    };
  }, [mode, whepUrl, hlsUrl]);

  useEffect(() => {
    if (mode !== "hls" || !hlsUrl || !videoRef.current) return;
    const video = videoRef.current;
    let active = true;
    let hls: HlsType | null = null;
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = hlsUrl;
      video.addEventListener("loadedmetadata", () => {
        video.play().catch((e) => console.warn("Autoplay prevenido por el navegador", e));
      }, { once: true });
    } else {
      void import("hls.js").then(({ default: Hls }) => {
        if (!active) return;
        if (!Hls.isSupported()) {
          setError("Este navegador no admite HLS.");
          return;
        }
        hls = new Hls({ enableWorker: true, lowLatencyMode: true });
        hls.loadSource(hlsUrl);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          video.play().catch((e) => console.warn("Autoplay prevenido por el navegador", e));
        });
        hls.on(Hls.Events.ERROR, (_event, data) => {
          if (data.fatal) setError("La reproducción HLS no está disponible.");
        });
      }).catch(() => {
        if (active) setError("No fue posible cargar el reproductor HLS.");
      });
    }
    return () => {
      active = false;
      hls?.destroy();
      video.removeAttribute("src");
      video.load();
    };
  }, [mode, hlsUrl]);

  if (mode === "unavailable") {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-media-background p-6 text-center text-media-muted">
        <div className="mb-4 flex size-14 items-center justify-center rounded-2xl bg-media-foreground/5 ring-1 ring-media-foreground/10">
          <VideoOff className="size-7 text-media-muted" />
        </div>
        <strong className="text-lg font-semibold text-media-foreground">Vídeo no disponible</strong>
        <span className="mt-1 max-w-sm text-sm leading-5 text-media-muted">{error ?? "MediaMTX no proporcionó endpoints de reproducción."}</span>
      </div>
    );
  }

  return (
    <div className="group relative h-full w-full bg-media-background">
      <video 
        ref={videoRef} 
        controls 
        autoPlay 
        playsInline 
        muted 
        aria-label="Transmisión en vivo" 
        className="w-full h-full object-contain"
      />
      
      <div className="absolute top-2 left-2 flex gap-2 pointer-events-none transition-opacity opacity-70 group-hover:opacity-100">
        <Badge variant="secondary" className="border-none bg-overlay text-media-foreground backdrop-blur-sm">
          {mode === "webrtc" ? "WebRTC · WHEP" : "HLS"}
        </Badge>
        {error && mode === "hls" ? (
          <Badge variant="destructive" className="border-none bg-destructive/80 text-destructive-foreground backdrop-blur-sm gap-1">
            <AlertCircle className="size-3" />
            WebRTC falló
          </Badge>
        ) : null}
      </div>
    </div>
  );
}
