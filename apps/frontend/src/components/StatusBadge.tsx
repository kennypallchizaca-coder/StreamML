import { Badge } from "./ui/badge";

interface StatusBadgeProps {
  value?: string | null;
  label?: string;
}

const positive = new Set(["connected", "online", "active", "streaming", "available", "ready", "vinculado"]);
const warning = new Set(["connecting", "reconnecting", "pending", "stale"]);

export default function StatusBadge({ value, label }: StatusBadgeProps) {
  const normalized = value?.trim().toLowerCase();
  const tone = normalized ? (positive.has(normalized) ? "default" : warning.has(normalized) ? "secondary" : "outline") : "outline";
  
  return (
    <Badge variant={tone}>
      {label ?? value ?? "No disponible"}
    </Badge>
  );
}
