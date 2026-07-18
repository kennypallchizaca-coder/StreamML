import { useEffect, useState } from "react";
import { api, normalizeSessions } from "../api";
import type { StreamSession } from "../types";
import { Card, CardContent } from "../components/ui/card";
import { Clock, VideoOff, Wifi, ShieldAlert, Check, HelpCircle } from "@/components/icons";
import { Badge } from "../components/ui/badge";
import PageHeader from "../components/PageHeader";
import { needsQualityAttention } from "../lib/sessionPresentation";

type AlertItem = {
  id: string;
  type: "warning" | "error" | "info";
  title: string;
  description: string;
  time: string;
  stream: string;
  recommendation: string;
};

function AlertIcon({ type }: { type: AlertItem["type"] }) {
  if (type === "error") return <VideoOff className="size-5 text-destructive" />;
  if (type === "warning") return <Wifi className="size-5 text-warning" />;
  return <ShieldAlert className="size-5 text-info" />;
}

function AlertList({ alerts, emptyText }: { alerts: AlertItem[], emptyText: string }) {
  if (alerts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground bg-muted/20 rounded-xl border border-dashed">
        <Check className="size-8 mb-2 opacity-30" />
        <p className="text-sm">{emptyText}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {alerts.map(alert => (
        <Card key={alert.id} className="border-l-4 border-l-warning">
          <CardContent className="p-4 sm:p-6 flex flex-col sm:flex-row gap-4">
            <div className="bg-muted p-3 rounded-full h-fit w-fit">
              <AlertIcon type={alert.type} />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <h4 className="font-semibold text-lg">{alert.title}</h4>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Clock className="size-3" /> {alert.time}
                  <Badge variant="outline" className="ml-2">{alert.stream}</Badge>
                </div>
              </div>
              <p className="text-muted-foreground text-sm">{alert.description}</p>
              
              <div className="mt-4 p-3 bg-primary/5 rounded-lg border border-primary/10">
                <p className="text-sm font-medium flex items-center gap-2">
                  <HelpCircle className="size-4 text-primary" />
                  Recomendación:
                </p>
                <p className="text-sm text-muted-foreground mt-1">{alert.recommendation}</p>
              </div>
            </div>
            <div className="flex flex-col justify-between items-end gap-2 shrink-0">
              <Badge variant="secondary" className="bg-warning/10 text-warning">Registrada</Badge>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function AlertsPage() {
  const [sessions, setSessions] = useState<StreamSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void api.listSessions().then((response) => {
      if (active) setSessions(normalizeSessions(response));
    }).catch((reason) => {
      if (!active) return;
      setError(reason instanceof Error ? reason.message : "No se pudieron cargar las alertas.");
      setSessions([]);
    });
    return () => { active = false; };
  }, []);

  const dynamicAlerts = { today: [] as AlertItem[], week: [] as AlertItem[], older: [] as AlertItem[] };

  if (sessions) {
    const now = new Date();
    sessions.forEach(session => {
      if (needsQualityAttention(session.latest_prediction?.recommendation)) {
        const sessionDate = new Date(session.latest_prediction?.created_at || session.updated_at || session.created_at || "");
        const isToday = sessionDate.toDateString() === now.toDateString();
        const diffDays = Math.floor((now.getTime() - sessionDate.getTime()) / (1000 * 3600 * 24));
        
        const alert: AlertItem = {
          id: session.id,
          type: "warning",
          title: "Inestabilidad registrada",
          description: `El modelo informó la recomendación ${session.latest_prediction?.recommendation}.`,
          time: sessionDate.toLocaleString(),
          stream: session.name || "Sin nombre",
          recommendation: "Revisa tu conexión a internet antes de tu próxima transmisión.",
        };

        if (isToday) dynamicAlerts.today.push(alert);
        else if (diffDays <= 7) dynamicAlerts.week.push(alert);
        else dynamicAlerts.older.push(alert);
      }
    });
  }

  return (
    <div className="app-page max-w-5xl">
      <PageHeader eyebrow="Seguimiento" title="Alertas" description="Revisa notificaciones y recomendaciones sobre tus transmisiones." />

      {error ? <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{error}</div> : null}

      <div className="space-y-10">
        <section>
          <h3 className="text-lg font-semibold mb-4 border-b pb-2">Hoy</h3>
          <AlertList alerts={dynamicAlerts.today} emptyText="No hay recomendaciones de reducción registradas hoy." />
        </section>

        <section>
          <h3 className="text-lg font-semibold mb-4 border-b pb-2">Esta semana</h3>
          <AlertList alerts={dynamicAlerts.week} emptyText="No hay recomendaciones de reducción registradas esta semana." />
        </section>

        <section>
          <h3 className="text-lg font-semibold mb-4 border-b pb-2">Anteriores</h3>
          <AlertList alerts={dynamicAlerts.older} emptyText="No hay alertas antiguas." />
        </section>
      </div>
    </div>
  );
}
