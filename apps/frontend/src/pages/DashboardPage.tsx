import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, normalizeSessions } from "../api";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "../components/ui/card";
import { Radio, Clock, Activity, ChevronRight, ExternalLink, Settings2, Video } from "lucide-react";
import type { StreamSession } from "../types";
import { useAuth } from "../App";
import PageHeader from "../components/PageHeader";

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

  const userName = user?.display_name || user?.email?.split('@')[0] || "Usuario";
  const recent = sessions?.slice(0, 3) ?? [];
  const activeSessions = sessions?.filter((session) => ["active", "live", "streaming"].includes(session.status?.toLowerCase() ?? ""));

  const lastActivity = sessions?.reduce<string | null>((latest, session) => {
    const candidate = session.updated_at || session.created_at;
    if (!candidate) return latest;
    return !latest || new Date(candidate).getTime() > new Date(latest).getTime() ? candidate : latest;
  }, null);

  const recommendations = recent.map(s => s.latest_prediction?.recommendation).filter(Boolean);
  const recommendationCounts = recommendations.reduce((acc, recommendation) => {
    acc[recommendation as string] = (acc[recommendation as string] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  const topRecommendation = Object.keys(recommendationCounts).sort((a, b) => recommendationCounts[b] - recommendationCounts[a])[0];
  const recommendationLabel: Record<string, string> = {
    maintain: "Mantener perfil",
    downgrade: "Reducir perfil",
    downgrade_needed: "Reducir perfil",
    upgrade: "Aumentar perfil",
  };

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Panel principal"
        title={`¡Hola, ${userName}!`}
        description="Aquí tienes un resumen del estado de tus transmisiones."
        action={<>
          <Button variant="outline" size="lg" className="w-full gap-2 sm:w-auto" asChild>
            <a href="http://127.0.0.1:8765/" target="_blank" rel="noopener noreferrer">
              <Settings2 className="size-5" />
              Configurar equipo <ExternalLink className="size-4" />
            </a>
          </Button>
          <Button size="lg" className="w-full gap-2 sm:w-auto" asChild>
            <Link to="/sessions/new">
              <Radio className="size-5" />
              Iniciar nueva transmisión
            </Link>
          </Button>
        </>}
      />

      {error ? <div className="text-sm font-medium text-destructive p-4 border border-destructive/20 bg-destructive/10 rounded-lg" role="alert">{error}</div> : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Transmisiones realizadas</CardTitle>
            <Video className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{sessions ? sessions.length : "--"}</div>
            <p className="text-xs text-muted-foreground mt-1">En el historial</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Última actividad</CardTitle>
            <Clock className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold">{sessions ? (lastActivity ? new Date(lastActivity).toLocaleDateString() : "No disponible") : "--"}</div>
            <p className="mt-1 text-xs text-muted-foreground">Según la sesión más reciente</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recomendación predominante</CardTitle>
            <Activity className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-xl font-bold ${topRecommendation ? "text-foreground" : "text-muted-foreground"}`}>
              {topRecommendation ? (recommendationLabel[topRecommendation] ?? topRecommendation) : "No disponible"}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Entre las últimas sesiones con predicción</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Transmisiones activas</CardTitle>
            <Radio className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeSessions ? activeSessions.length : "--"}</div>
            <p className="text-xs text-muted-foreground mt-1">En curso ahora mismo</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(17rem,0.85fr)]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between border-b bg-muted/20 pb-4">
            <div className="space-y-1">
              <CardTitle>Últimas transmisiones</CardTitle>
              <CardDescription>Revisa el estado de tus eventos más recientes.</CardDescription>
            </div>
            <Button variant="ghost" size="sm" className="gap-1" asChild>
              <Link to="/history">
                Ver todo <ChevronRight className="size-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {sessions === null && !error ? <div className="text-sm text-muted-foreground text-center py-8">Cargando...</div> : null}
            {sessions?.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center px-4">
                <Video className="size-10 text-muted-foreground opacity-50 mb-4" />
                <h3 className="font-semibold text-lg">Aún no hay transmisiones</h3>
                <p className="text-sm text-muted-foreground mt-1">Crea tu primera transmisión para comenzar a monitorear la calidad en tiempo real.</p>
                <Button variant="outline" className="mt-6" asChild><Link to="/sessions/new">Crear transmisión</Link></Button>
              </div>
            ) : null}
            {recent.length > 0 && (
              <div className="divide-y">
                {recent.map((session) => (
                  <div key={session.id} className="flex flex-col sm:flex-row sm:items-center justify-between p-4 gap-4 hover:bg-muted/5 transition-colors">
                    <div className="flex flex-col gap-1">
                      <span className="font-semibold text-base">{session.name || `Transmisión del ${new Date(session.created_at || "").toLocaleDateString()}`}</span>
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="size-3" />
                        {session.created_at ? new Date(session.created_at).toLocaleString() : "Fecha no disponible"}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 self-end sm:self-auto">
                      <Badge variant={
                        ["connected", "online", "active", "streaming", "available", "ready", "vinculado"].includes(session.status?.trim().toLowerCase() ?? "") ? "default" :
                        ["connecting", "reconnecting", "pending", "stale"].includes(session.status?.trim().toLowerCase() ?? "") ? "secondary" : "outline"
                      } className={session.status === "active" ? "bg-green-500 hover:bg-green-600" : ""}>
                        {session.status === "active" ? "En vivo" : "Finalizada"}
                      </Badge>
                      <Button variant="outline" size="sm" asChild>
                        <Link to={session.status === "active" ? `/sessions/${encodeURIComponent(session.id)}/live` : `/history`}>
                          {session.status === "active" ? "Monitorear" : "Detalles"}
                        </Link>
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Estado de la cuenta</CardTitle>
            <CardDescription>Resumen de tus servicios.</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col gap-4">
            <div className="p-4 rounded-xl border bg-card flex items-center gap-3">
              <div className="size-10 rounded-full bg-green-500/10 flex items-center justify-center text-green-500">
                <Activity className="size-5" />
              </div>
              <div>
                <div className="font-medium">Sesión autenticada</div>
                <div className="text-xs text-muted-foreground">Panel y servicios de cuenta disponibles</div>
              </div>
            </div>
            
            {activeSessions && activeSessions.length > 0 ? (
              <div className="p-4 rounded-xl border bg-primary/5 border-primary/20 flex flex-col gap-2">
                <div className="font-medium text-primary">Tienes un evento en vivo</div>
                <Button size="sm" className="w-full" asChild>
                  <Link to={`/sessions/${encodeURIComponent(activeSessions[0].id)}/live`}>
                    Ir a transmisión
                  </Link>
                </Button>
              </div>
            ) : (
              <div className="p-4 rounded-xl border bg-muted/20 text-center flex-1 flex flex-col justify-center items-center">
                <span className="text-sm text-muted-foreground">No tienes transmisiones activas en este momento.</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
