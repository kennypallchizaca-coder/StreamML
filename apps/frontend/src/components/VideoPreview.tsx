import { useState, useEffect } from "react";
import VdoNinjaCamera from "./VdoNinjaCamera";
import VideoConnectionStatus from "./VideoConnectionStatus";

interface VideoPreviewProps {
  embedUrl: string;
  isLiveMonitor?: boolean;
  onStatus?: (status: string) => void;
}

export default function VideoPreview({ embedUrl, isLiveMonitor, onStatus }: VideoPreviewProps) {
  const [loading, setLoading] = useState(true);
  const [videoStatus, setVideoStatus] = useState<"connected" | "waiting" | "error">("waiting");

  useEffect(() => {
    setLoading(true);
    setVideoStatus("waiting");
  }, [embedUrl]);

  function handleStatus(status: string) {
    const normalized = status.toLowerCase();
    if (["connected", "active", "streaming", "view-connection"].includes(normalized)) {
      setVideoStatus("connected");
    } else if (["disconnected", "failed", "error"].includes(normalized)) {
      setVideoStatus("error");
    }
    onStatus?.(status);
  }

  // Mask the URL for display
  const maskedUrl = embedUrl 
    ? embedUrl.replace(/([?&](?:push|view|room)=)([^&]+)/, "$1••••••••") 
    : "";

  return (
    <div className="flex flex-col gap-2 w-full h-full">
      {!isLiveMonitor && (
        <div className="flex justify-between items-center mb-1">
          <h4 className="font-semibold">Vista previa de la cámara</h4>
          <VideoConnectionStatus status={videoStatus} />
        </div>
      )}
      
      <div className="relative flex min-h-64 w-full flex-1 items-center justify-center overflow-hidden rounded-2xl bg-media-background">
        <VdoNinjaCamera
          embedUrl={embedUrl}
          onLoad={() => setLoading(false)}
          onStatus={handleStatus}
        />
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-media-background/85 text-media-foreground backdrop-blur-sm">
            <span className="font-medium">Conectando al video…</span>
          </div>
        )}
      </div>
      
      {!isLiveMonitor && (
        <div className="mt-2 text-center">
          <p className="text-xs font-mono text-muted-foreground break-all bg-muted/30 p-1 rounded inline-block max-w-full truncate px-2">
            {maskedUrl}
          </p>
          <p className="text-xs text-muted-foreground mt-2">Asegúrate de permitir el acceso a la cámara en tu teléfono.</p>
        </div>
      )}
    </div>
  );
}
