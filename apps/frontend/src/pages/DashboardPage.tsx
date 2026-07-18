import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clock3,
  ExternalLink,
  History,
  LoaderCircle,
  Radio,
  Settings2,
  ShieldCheck,
  Video,
} from "@/components/icons";
import { api, normalizeSessions } from "../api";
import { useAuth } from "../App";
import PageHeader from "../components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import type { StreamSession } from "../types";
import { isSessionLive, sessionStateLabel } from "../lib/sessionPresentation";
import NexaMascot from "../components/NexaMascot";

function formatDate(value?: string | null, compact = false) {
  if (!value) return "No disponible";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No disponible";
  return date.toLocaleString("es-EC", compact
    ? { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }
    : { dateStyle: "medium", timeStyle: "short" });
}

function localSetupUrl() {
  const theme = document.documentElement.classList.contains("dark") ? "dark" : "light";
  return `http://127.0.0.1:8765/?theme=${theme}`;
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: string | number;
  icon: typeof Video;
  tone?: "default" | "success";
}) {
  return (
    <Card className="relative overflow-hidden py-5">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle>
          <p className="text-2xl font-semibold tracking-[-0.035em] tabular-nums sm:text-3xl">{value}</p>
        </div>
        <span className={`flex size-9 shrink-0 items-center justify-center rounded-lg border ${tone === "success" ? "border-success/20 bg-success/10 text-success" : "bg-muted/40 text-muted-foreground"}`}>
          <Icon className="size-4" />
        </span>
      </CardHeader>
    </Card>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<StreamSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void api.listSessions()
      .then((response) => { if (active) setSessions(normalizeSessions(response)); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "No pudimos cargar tus datos en este momento."); });
    return () => { active = false; };
  }, []);

  const userName = user?.display_name || user?.email?.split("@")[0] || "Usuario";
  const activeSessions = useMemo(() => sessions?.filter((session) => isSessionLive(session.status)) ?? [], [sessions]);
  const recent = useMemo(() => sessions?.slice(0, 5) ?? [], [sessions]);
  const predictionSessions = sessions?.filter((session) => Boolean(session.latest_prediction)) ?? [];
  const lastActivity = sessions?.reduce<string | null>((latest, session) => {
    const candidate = session.updated_at || session.created_at;
    if (!candidate) return latest;
    return !latest || new Date(candidate).getTime() > new Date(latest).getTime() ? candidate : latest;
  }, null);

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Centro de control"
        title="Resumen operativo"
        description={`Hola, ${userName}. Estado actual de StreamML.`}
        action={(
          <Button variant="outline" className="w-full gap-2 sm:w-auto" asChild>
            <a href={localSetupUrl()} onClick={(event) => { event.currentTarget.href = localSetupUrl(); }} target="_blank" rel="noopener noreferrer">
              <Settings2 />Abrir conector<ExternalLink className="size-3.5" />
            </a>
          </Button>
        )}
      />

      {error ? (
        <Alert variant="destructive" role="alert">
          <AlertTitle>No pudimos actualizar el panel</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <section aria-label="Indicadores principales" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Transmisiones"
          value={sessions ? sessions.length : "—"}
          icon={Video}
        />
        <StatCard
          label="En vivo ahora"
          value={sessions ? activeSessions.length : "—"}
          icon={Radio}
          tone={activeSessions.length ? "success" : "default"}
        />
        <StatCard
          label="Sesiones con predicción"
          value={sessions ? predictionSessions.length : "—"}
          icon={BrainCircuit}
        />
        <StatCard
          label="Última actividad"
          value={sessions ? (lastActivity ? formatDate(lastActivity, true).split(",")[0] : "Sin datos") : "—"}
          icon={Clock3}
        />
      </section>

      <section className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.75fr)_minmax(18rem,0.75fr)]">
        <Card className="overflow-hidden">
          <CardHeader className="flex flex-row items-start justify-between gap-4 border-b pb-5">
            <CardTitle>Actividad reciente</CardTitle>
            <Button variant="ghost" size="sm" className="-mr-2 gap-1 text-muted-foreground" asChild>
              <Link to="/history">Ver historial<ChevronRight /></Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {sessions === null && !error ? (
              <div className="flex min-h-64 items-center justify-center gap-2 text-sm text-muted-foreground" aria-live="polite">
                <LoaderCircle className="size-4 animate-spin" />Cargando actividad…
              </div>
            ) : null}
            {sessions?.length === 0 ? (
              <div className="flex min-h-64 flex-col items-center justify-center px-6 py-10 text-center">
                <span className="mb-4 flex size-12 items-center justify-center rounded-xl border bg-muted/30 text-muted-foreground"><Video className="size-5" /></span>
                <h3 className="font-medium">Todavía no hay transmisiones</h3>
                <p className="mt-1 max-w-sm text-sm leading-6 text-muted-foreground">Crea la primera sesión para vincular OBS, recibir telemetría y activar las recomendaciones ML.</p>
                <Button className="mt-5" asChild><Link to="/sessions/new"><Radio />Crear transmisión</Link></Button>
              </div>
            ) : null}
            {recent.length ? (
              <div className="divide-y divide-border/70">
                {recent.map((session) => {
                  const active = isSessionLive(session.status);
                  return (
                    <div key={session.id} className="group flex flex-col gap-4 px-5 py-4 transition-colors hover:bg-muted/20 sm:flex-row sm:items-center sm:px-6">
                      <span className={`flex size-9 shrink-0 items-center justify-center rounded-lg border ${active ? "border-success/20 bg-success/10 text-success" : "bg-muted/30 text-muted-foreground"}`}>
                        {active ? <CircleDot className="size-4" /> : <History className="size-4" />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{session.name || "Transmisión sin nombre"}</p>
                        <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                          <Clock3 className="size-3" />{formatDate(session.created_at, true)}
                          {session.configuration?.platform ? <><span aria-hidden="true">·</span><span className="capitalize">{session.configuration.platform}</span></> : null}
                        </p>
                      </div>
                      <div className="flex items-center justify-between gap-3 sm:justify-end">
                        <Badge variant={active ? "default" : "outline"} className={active ? "border-success/20 bg-success/10 text-success hover:bg-success/15" : "font-normal text-muted-foreground"}>
                          {sessionStateLabel(session.status)}
                        </Badge>
                        <Button variant="ghost" size="icon-sm" asChild aria-label={active ? `Monitorear ${session.name || "transmisión"}` : "Abrir historial"}>
                          <Link to={active ? `/sessions/${encodeURIComponent(session.id)}/live` : "/history"}><ArrowUpRight /></Link>
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="grid content-start gap-4">
          <Card className="agent-card overflow-hidden border-agent/30">
            <CardContent className="flex items-center gap-4 py-5">
              <NexaMascot mood={activeSessions.length ? "observing" : "waiting"} size="compact" />
              <div className="min-w-0">
                <Badge variant="outline" className="border-agent/35 text-agent">Agente IA</Badge>
                <h2 className="mt-2 text-lg font-semibold tracking-tight">Hola, soy Nexa</h2>
                <p className="mt-1 line-clamp-2 text-sm leading-5 text-muted-foreground">
                  {activeSessions.length
                    ? `Estoy supervisando ${activeSessions.length === 1 ? "una transmisión activa" : `${activeSessions.length} transmisiones activas`} y sus decisiones de calidad.`
                    : "Estoy lista para acompañar tu próxima transmisión y explicar cada decisión de calidad."}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Estado del sistema</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-1">
              <div className="flex items-center gap-3 rounded-lg px-2 py-3">
                <span className="flex size-8 items-center justify-center rounded-lg bg-success/10 text-success"><ShieldCheck className="size-4" /></span>
                <div className="min-w-0 flex-1"><p className="text-sm font-medium">Acceso seguro</p><p className="text-xs text-muted-foreground">Sesión autenticada</p></div>
                <CheckCircle2 className="size-4 text-success" />
              </div>
              <div className="flex items-center gap-3 rounded-lg px-2 py-3">
                <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary"><Activity className="size-4" /></span>
                <div className="min-w-0 flex-1"><p className="text-sm font-medium">Datos operativos</p><p className="text-xs text-muted-foreground">{sessions?.length ? `${sessions.length} sesiones disponibles` : "Esperando la primera sesión"}</p></div>
                <span className={`size-2 rounded-full ${sessions?.length ? "bg-success" : "bg-muted-foreground/40"}`} />
              </div>
              <div className="flex items-center gap-3 rounded-lg px-2 py-3">
                <span className="flex size-8 items-center justify-center rounded-lg bg-prediction/10 text-prediction"><BrainCircuit className="size-4" /></span>
                <div className="min-w-0 flex-1"><p className="text-sm font-medium">Predicción ML</p><p className="text-xs text-muted-foreground">{predictionSessions.length ? "Decisiones registradas" : "Sin predicciones recientes"}</p></div>
                <span className={`size-2 rounded-full ${predictionSessions.length ? "bg-success" : "bg-muted-foreground/40"}`} />
              </div>
            </CardContent>
          </Card>

        </div>
      </section>
    </div>
  );
}
