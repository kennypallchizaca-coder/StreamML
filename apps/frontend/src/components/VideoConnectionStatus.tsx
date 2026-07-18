import { CheckCircle2, AlertTriangle, Loader2 } from "@/components/icons";

interface VideoConnectionStatusProps {
  status: "connected" | "waiting" | "error";
  message?: string;
}

export default function VideoConnectionStatus({ status, message }: VideoConnectionStatusProps) {
  if (status === "connected") {
    return (
      <div className="flex w-fit max-w-full items-center gap-2 rounded-full border border-success/20 bg-success/10 px-3 py-1.5 text-sm text-success">
        <CheckCircle2 className="size-4 shrink-0" />
        <span className="truncate font-medium">{message || "Video conectado"}</span>
      </div>
    );
  }

  if (status === "waiting") {
    return (
      <div className="flex w-fit max-w-full items-center gap-2 rounded-full border border-warning/20 bg-warning/10 px-3 py-1.5 text-sm text-warning">
        <Loader2 className="size-4 shrink-0 animate-spin" />
        <span className="truncate font-medium">{message || "Esperando video"}</span>
      </div>
    );
  }

  return (
    <div className="flex w-fit max-w-full items-center gap-2 rounded-full border border-destructive/20 bg-destructive/10 px-3 py-1.5 text-sm text-destructive">
      <AlertTriangle className="size-4 shrink-0" />
      <span className="truncate font-medium">{message || "Video desconectado"}</span>
    </div>
  );
}
