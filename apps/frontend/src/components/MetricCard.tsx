import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

interface MetricCardProps {
  label: string;
  value?: ReactNode;
  unit?: string;
  hint?: string;
}

export default function MetricCard({ label, value, unit, hint }: MetricCardProps) {
  const hasValue = value !== null && value !== undefined && value !== "";
  return (
    <Card className="gap-3 py-5">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-14 flex-col justify-center">
        <div className={`text-wrap text-2xl font-semibold tabular-nums tracking-tight ${!hasValue ? 'text-base text-muted-foreground' : ''}`}>
          {hasValue ? value : "No disponible"}
          {hasValue && unit ? <span className="ml-1 text-sm font-normal text-muted-foreground">{unit}</span> : null}
        </div>
        {hint ? <p className="mt-1 text-xs leading-5 text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}
