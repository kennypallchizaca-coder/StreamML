import type HlsType from "hls.js";
import { useEffect, useRef, useState } from "react";
import { AlertCircle, VideoOff } from "@/components/icons";
import { Badge } from "./ui/badge";

interface MediaMtxPlayerProps {
  whepUrl?: string | null;
  hlsUrl?: string | null;
  mediaStatus?: string | null;
}

type PlaybackMode = "webrtc" | "hls" | "unavailable";

const NO_LIVE_SIGNAL_MESSAGE =
  "No hay una señal publicada para esta sesión. Copia el servidor y la clave de esta sesión en OBS, inicia la transmisión y vuelve a intentarlo.";
const PLAYBACK_RETRY_MS = 3_000;
const HLS_STARTUP_TIMEOUT_MS = 8_000;
const HLS_STARTUP_RETRY_MAX_MS = 20_000;
const SESSION_SIGNAL_MISSING_MESSAGE =
  "MediaMTX no recibe una señal para esta sesión. Verifica que OBS use el servidor y la clave RTMP mostrados en esta pantalla.";

function preferredPlaybackMode(hlsUrl?: string | null, whepUrl?: string | null): PlaybackMode {
  // OBS can legitimately emit H264 with B-frames. MediaMTX cannot relay
  // that format through WebRTC/WHEP, while LL-HLS plays it reliably in the
  // browsers we support. Prefer HLS so a failed WebRTC negotiation never
  // leaves a healthy stream on a black preview.
  if (hlsUrl) return "hls";
  if (whepUrl) return "webrtc";
  return "unavailable";
}

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

export default function MediaMtxPlayer({ whepUrl, hlsUrl, mediaStatus }: MediaMtxPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsStartupRetriesRef = useRef(0);
  const [mode, setMode] = useState<PlaybackMode>(() => preferredPlaybackMode(hlsUrl, whepUrl));
  const [error, setError] = useState<string | null>(null);
  const [hlsReloadGeneration, setHlsReloadGeneration] = useState(0);
  const serverHasNoSignal = mediaStatus === "disconnected" || mediaStatus === "waiting";

  useEffect(() => {
    if (serverHasNoSignal) {
      setMode("unavailable");
      setError(SESSION_SIGNAL_MISSING_MESSAGE);
      return;
    }
    setMode(preferredPlaybackMode(hlsUrl, whepUrl));
    setError(null);
    hlsStartupRetriesRef.current = 0;
    setHlsReloadGeneration(0);
  }, [whepUrl, hlsUrl, serverHasNoSignal]);

  useEffect(() => {
    if (mode !== "unavailable" || serverHasNoSignal || (!whepUrl && !hlsUrl)) return;
    // MediaMTX intentionally returns 404 while an RTMP publisher is offline.
    // Keep probing at a bounded interval so a recovered publisher becomes
    // visible without requiring the operator to reload the entire page.
    const retry = window.setTimeout(() => {
      setError(null);
      setMode(preferredPlaybackMode(hlsUrl, whepUrl));
    }, PLAYBACK_RETRY_MS);
    return () => window.clearTimeout(retry);
  }, [mode, whepUrl, hlsUrl, serverHasNoSignal]);

  useEffect(() => {
    if (mode !== "webrtc" || !whepUrl || !videoRef.current) return;
    const controller = new AbortController();
    const peer = new RTCPeerConnection();
    const video = videoRef.current;
    let resourceUrl: string | null = null;
    let remoteSessionClosed = false;

    peer.addTransceiver("video", { direction: "recvonly" });
    peer.addTransceiver("audio", { direction: "recvonly" });
    peer.ontrack = (event) => {
      video.srcObject = event.streams[0];
      video.play().catch((e) => console.warn("Autoplay prevenido por el navegador", e));
    };
    peer.onconnectionstatechange = () => {
      if (["failed", "disconnected"].includes(peer.connectionState)) remoteSessionClosed = true;
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
        const noLiveSignal = reason instanceof Error && reason.message.includes("404");
        setError(noLiveSignal ? NO_LIVE_SIGNAL_MESSAGE : "No fue posible iniciar WebRTC.");
        // A WHEP 404 is MediaMTX's explicit response that this path has no
        // publisher. HLS cannot recover a stream that does not exist.
        setMode(noLiveSignal ? "unavailable" : hlsUrl ? "hls" : "unavailable");
      }
    })();

    return () => {
      controller.abort();
      peer.close();
      video.srcObject = null;
      // A failed WebRTC negotiation can make MediaMTX dispose of the WHEP
      // resource first (for example, when the incoming H264 has B-frames).
      // Avoid a guaranteed 404 while falling back to HLS.
      if (resourceUrl && !remoteSessionClosed) void fetch(resourceUrl, { method: "DELETE", credentials: "omit" }).catch(() => undefined);
    };
  }, [mode, whepUrl, hlsUrl]);

  useEffect(() => {
    if (mode !== "hls" || !hlsUrl || !videoRef.current) return;
    const video = videoRef.current;
    let active = true;
    let playable = false;
    let hls: HlsType | null = null;
    const markPlayable = () => {
      playable = true;
      hlsStartupRetriesRef.current = 0;
      setError(null);
    };
    const startupTimeout = window.setTimeout(() => {
      if (!active || playable) return;
      const retryDelay = Math.min(
        HLS_STARTUP_TIMEOUT_MS + hlsStartupRetriesRef.current * PLAYBACK_RETRY_MS,
        HLS_STARTUP_RETRY_MAX_MS,
      );
      hlsStartupRetriesRef.current += 1;
      setError("La señal se está preparando; reconectando la vista previa…");
      // A stream can become available after Hls.js has already accepted an
      // empty initial playlist. That state does not always produce a fatal
      // event, so recreate the player instead of requiring a page reload.
      window.setTimeout(() => {
        if (active) setHlsReloadGeneration((generation) => generation + 1);
      }, retryDelay - HLS_STARTUP_TIMEOUT_MS);
    }, HLS_STARTUP_TIMEOUT_MS);
    video.addEventListener("loadeddata", markPlayable, { once: true });
    video.addEventListener("playing", markPlayable, { once: true });
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
        hls = new Hls({
          enableWorker: true,
          lowLatencyMode: true,
          // MediaMTX authorizes the manifest and media parts through its
          // cookie-check flow. Keep that same-origin cookie on every HLS
          // request instead of allowing a manifest-only black player.
          xhrSetup: (xhr) => {
            xhr.withCredentials = true;
          },
        });
        hls.loadSource(hlsUrl);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          video.play().catch((e) => console.warn("Autoplay prevenido por el navegador", e));
        });
        hls.on(Hls.Events.FRAG_BUFFERED, markPlayable);
        hls.on(Hls.Events.ERROR, (_event, data) => {
          if (data.fatal) {
            setError(data.response?.code === 404 ? NO_LIVE_SIGNAL_MESSAGE : "La reproducción HLS no está disponible.");
            setMode("unavailable");
          }
        });
      }).catch(() => {
        if (active) setError("No fue posible cargar el reproductor HLS.");
      });
    }
    return () => {
      active = false;
      window.clearTimeout(startupTimeout);
      hls?.destroy();
      video.removeEventListener("loadeddata", markPlayable);
      video.removeEventListener("playing", markPlayable);
      video.removeAttribute("src");
      video.load();
    };
  }, [mode, hlsUrl, hlsReloadGeneration]);

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
            Reconectando vídeo
          </Badge>
        ) : null}
      </div>
    </div>
  );
}
