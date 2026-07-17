import type { JSX } from "react";
import type { FeatureAvailability } from "../types";
import { Badge } from "./ui/badge";
import { CheckCircle2, XCircle, AlertCircle, HelpCircle } from "lucide-react";

const labels: Record<FeatureAvailability["state"], string> = {
  available: "Disponible",
  missing: "Faltante",
  stale: "Desactualizada",
  unsupported: "No compatible",
};

const StatusIcons: Record<FeatureAvailability["state"], JSX.Element> = {
  available: <CheckCircle2 className="size-4 text-emerald-500" />,
  missing: <XCircle className="size-4 text-destructive" />,
  stale: <AlertCircle className="size-4 text-amber-500" />,
  unsupported: <HelpCircle className="size-4 text-muted-foreground" />,
};

export default function FeatureState({ feature }: { feature: FeatureAvailability }) {
  const tone = feature.state === "available" ? "default" : feature.state === "missing" ? "destructive" : feature.state === "stale" ? "secondary" : "outline";
  
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-xl border bg-card p-3.5 text-card-foreground shadow-sm">
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <span className="flex min-w-0 items-start gap-2">
          <span className="mt-0.5 shrink-0">{StatusIcons[feature.state]}</span>
          <span className="min-w-0">
            <strong className="block text-wrap font-medium leading-5">{feature.name}</strong>
            {feature.unit ? <span className="text-xs text-muted-foreground">Unidad: {feature.unit}</span> : null}
          </span>
        </span>
        <Badge variant={tone} className="w-fit shrink-0">{labels[feature.state]}</Badge>
      </div>
      {feature.reason ? <span className="pl-6 text-xs leading-5 text-muted-foreground">{feature.reason}</span> : null}
    </div>
  );
}
