import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api";
import MediaMtxPlayer from "../components/MediaMtxPlayer";
import VideoPreview from "../components/VideoPreview";
import ReplaceVideoLinkDialog from "../components/ReplaceVideoLinkDialog";
import useSessionSocket from "../hooks/useSessionSocket";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "../components/ui/card";
import { Activity, AlertTriangle, CheckCircle2, Clock, Pause, Play, Square, Info, Smartphone, Monitor, Server } from "@/components/icons";
import type { AgentDecision, PredictionSnapshot, StreamSession, TelemetrySnapshot, VideoEndpoints } from "../types";
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import PageHeader from "../components/PageHeader";
import FeatureState from "../components/FeatureState";

function translateRecommendation(rec?: string | null) {
  switch (rec) {
    case "high": return { title: "Usar perfil alto", priority: "Recomendación", action: "Resultado informado por el modelo. La decisión corresponde al usuario.", color: "text-info", border: "border-info/20" };
    case "medium": return { title: "Usar perfil medio", priority: "Recomendación", action: "Resultado informado por el modelo. La decisión corresponde al usuario.", color: "text-info", border: "border-info/20" };
    case "low": return { title: "Usar perfil básico", priority: "Recomendación", action: "Resultado informado por el modelo. La decisión corresponde al usuario.", color: "text-warning", border: "border-warning/20" };
    case "maintain": return { title: "Mantener perfil actual", priority: "Recomendación", action: "El modelo recomienda mantener; el agente decide la acción final.", color: "text-success", border: "border-success/20" };
    case "downgrade_needed": return { title: "Reducir perfil", priority: "Recomendación", action: "El modelo anticipa una reducción; el agente aplica la política de seguridad.", color: "text-warning", border: "border-warning/20" };
    default: return { title: "Esperando predicción", priority: "Pendiente", action: "Todavía no hay una recomendación compatible disponible.", color: "text-muted-foreground", border: "border-border" };
  }
}

function translateAgentDecision(decision?: AgentDecision | null) {
  const target = profileLabel(decision?.target_profile);
  switch (decision?.action) {
    case "increase": return { title: `Perfil aumentado a ${target}`, detail: decision.reason, tone: "text-success" };
    case "reduce": return { title: `Perfil reducido a ${target}`, detail: decision.reason, tone: "text-warning" };
    case "switch_to_backup": return { title: "Video de respaldo activado", detail: decision.reason, tone: "text-warning" };
    case "maintain_backup": return { title: "Respaldo activo", detail: decision.reason, tone: "text-warning" };
    case "restore_live": return { title: "Señal en vivo restaurada", detail: decision.reason, tone: "text-success" };
    case "maintain": return { title: `Perfil ${target} mantenido`, detail: decision.reason, tone: "text-info" };
    default: return { title: "Agente esperando telemetría", detail: "La primera decisión se mostrará al recibir datos del conector.", tone: "text-muted-foreground" };
  }
}

function translateRisk(prob?: number | null) {
  if (prob == null) return { level: "No disponible", color: "text-muted-foreground", text: "La API no informó una probabilidad válida." };
  const p = Math.round(prob * 100);
  return { level: "Probabilidad informada", color: "text-foreground", text: `Probabilidad de degradación según el modelo: ${p} %.` };
}

export function getGeneralState(telemetry: TelemetrySnapshot | null) {
  if (!telemetry) return { state: "Esperando telemetría", desc: "La API aún no ha recibido datos del conector.", color: "bg-muted text-muted-foreground", icon: Activity };
  if (telemetry.stream_reconnecting) {
    return { state: "Reconectando transmisión", desc: "OBS está intentando recuperar la salida de streaming.", color: "bg-warning/10 text-warning", icon: AlertTriangle };
  }
  if (telemetry.obs_status && !["connected", "online", "active", "streaming"].includes(telemetry.obs_status.toLowerCase())) {
    return { state: "Sin señal de OBS", desc: "El conector no recibe estadísticas de OBS en este momento.", color: "bg-muted text-muted-foreground", icon: AlertTriangle };
  }
  if (telemetry.stream_active === false) {
    return { state: "OBS conectado, transmisión detenida", desc: "La telemetría funciona, pero OBS todavía no está transmitiendo.", color: "bg-muted text-muted-foreground", icon: Info };
  }
  const hasNetworkMetrics = telemetry.packet_loss_percent != null || telemetry.latency_ms != null;
  return hasNetworkMetrics
    ? { state: "Telemetría recibida", desc: "OBS y las métricas de red disponibles están reportando datos.", color: "bg-info text-info-foreground", icon: CheckCircle2 }
    : { state: "Monitoreo parcial", desc: "OBS reporta datos, pero las métricas de red aún no están disponibles.", color: "bg-muted text-muted-foreground", icon: Info };
}

export function liveBadge(telemetry: TelemetrySnapshot | null) {
  if (telemetry?.stream_reconnecting) return { label: "RECONECTANDO", variant: "outline" as const, pulse: false };
  if (telemetry?.stream_active) return { label: "EN VIVO", variant: "destructive" as const, pulse: true };
  if (telemetry?.obs_status === "connected") return { label: "OBS LISTO", variant: "secondary" as const, pulse: false };
  return { label: "ESPERANDO SEÑAL", variant: "outline" as const, pulse: false };
}

function connectionLabel(value?: string | null) {
  if (!value) return "No disponible";
  const labels: Record<string, string> = {
    connected: "Conectado",
    online: "En línea",
    active: "Activo",
    streaming: "Transmitiendo",
    disconnected: "Desconectado",
    reconnecting: "Reconectando",
    pending: "Pendiente",
  };
  return labels[value.toLowerCase()] ?? value;
}

function profileLabel(value?: string | null) {
  if (!value) return "--";
  const labels: Record<string, string> = { high: "Alto", medium: "Medio", low: "Básico" };
  return labels[value.toLowerCase()] ?? value;
}

function modelRoleLabel(value?: string | null) {
  if (!value) return "Rol no disponible";
  const labels: Record<string, string> = { predictive: "Predictivo", reactive: "Reactivo" };
  return `Modelo ${labels[value.toLowerCase()] ?? value}`;
}

function modelStatusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    available: "Disponible",
    executed: "Ejecutado",
    blocked: "Esperando datos",
    pending: "Pendiente",
  };
  return value ? labels[value.toLowerCase()] ?? value : "Sin resultado";
}

export function latestPredictionByRole(
  predictions: PredictionSnapshot[],
  role: "reactive" | "predictive",
) {
  return predictions.find((prediction) => prediction.model_role?.toLowerCase() === role) ?? null;
}

function mergeLatestPredictions(
  incoming: PredictionSnapshot[],
  current: PredictionSnapshot[],
) {
  const candidates = [...incoming, ...current];
  return (["reactive", "predictive"] as const)
    .map((role) => latestPredictionByRole(candidates, role))
    .filter((prediction): prediction is PredictionSnapshot => prediction != null);
}

function ModelResultPanel({
  role,
  prediction,
}: {
  role: "reactive" | "predictive";
  prediction: PredictionSnapshot | null;
}) {
  const blocked = prediction?.status === "blocked";
  const recommendation = translateRecommendation(blocked ? null : prediction?.recommendation);
  const probability = prediction?.degradation_probability ?? prediction?.probability_downgrade_needed;
  const risk = translateRisk(blocked ? null : probability);
  const isReactive = role === "reactive";

  return (
    <section className="flex min-w-0 flex-col rounded-xl border bg-card p-5 shadow-sm" aria-label={`Resultado del modelo ${isReactive ? "reactivo" : "predictivo"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {isReactive ? "Condiciones actuales" : "Próximos 10 minutos"}
          </div>
          <h3 className="mt-1 text-lg font-semibold">Modelo {isReactive ? "reactivo" : "predictivo"}</h3>
        </div>
        <Badge variant={blocked ? "outline" : prediction ? "secondary" : "outline"}>
          {modelStatusLabel(prediction?.status)}
        </Badge>
      </div>

      <div className="mt-5 flex-1">
        <div className={`text-xl font-bold ${recommendation.color}`}>{recommendation.title}</div>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {prediction?.reason || recommendation.action}
        </p>
      </div>

      {!isReactive ? (
        <div className="mt-5 rounded-xl border bg-muted/20 p-4">
          <div className="flex items-center justify-between gap-4 text-sm">
            <span className="font-medium">Probabilidad de reducción</span>
            <span className={`text-lg font-bold ${risk.color}`}>
              {!blocked && probability != null ? `${Math.round(probability * 100)}%` : "--"}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{risk.text}</p>
        </div>
      ) : null}

      <div className="mt-5 flex flex-wrap gap-x-4 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
        <span>{prediction?.model_version ? `Versión ${prediction.model_version}` : "Versión no disponible"}</span>
        <span>{prediction?.created_at ? `Actualizado ${new Date(prediction.created_at).toLocaleTimeString("es-EC")}` : "Sin ejecución registrada"}</span>
      </div>
    </section>
  );
}

function metricNumber(value?: number | null, maximumFractionDigits = 1) {
  if (value == null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("es-EC", { maximumFractionDigits }).format(value);
}

export default function LiveMonitorPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState<StreamSession | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [predictions, setPredictions] = useState<PredictionSnapshot[]>([]);
  const [agentDecision, setAgentDecision] = useState<AgentDecision | null>(null);
  const [stream, setStream] = useState<VideoEndpoints | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [monitoring, setMonitoring] = useState(true);
  const socket = useSessionSocket(sessionId);

  const [hideVideo, setHideVideo] = useState(false);
  const [reconnectKey, setReconnectKey] = useState(0);
  const [phoneStatus, setPhoneStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    api.getSession(sessionId).then((s) => {
      setSession(s);
      setTelemetry(s.telemetry ?? null);
      setPredictions(mergeLatestPredictions(
        s.recent_predictions ?? (s.latest_prediction ? [s.latest_prediction] : []),
        [],
      ));
      setAgentDecision(s.agent_decision ?? null);
      setStream(s.stream ?? null);
    }).catch(() => setError("No pudimos conectar con tu transmisión. Verifica que esté activa e intenta nuevamente."));
    api.getStream(sessionId).then(setStream).catch(() => {
      setError("La sesión se cargó, pero no fue posible renovar los enlaces de reproducción de MediaMTX.");
    });
  }, [sessionId]);

  useEffect(() => {
    if (!monitoring || !socket.message) return;
    const { session, telemetry, prediction, predictions: incomingPredictions, stream, agent_decision } = socket.message;
    if (session) setSession(session);
    if (telemetry) setTelemetry(telemetry);
    if (incomingPredictions?.length) {
      setPredictions((current) => mergeLatestPredictions(incomingPredictions, current));
    } else if (prediction) {
      setPredictions((current) => mergeLatestPredictions([prediction], current));
    }
    if (agent_decision) setAgentDecision(agent_decision);
    if (stream) setStream(stream);
  }, [socket.message, monitoring]);

  const reactivePrediction = latestPredictionByRole(predictions, "reactive");
  const predictivePrediction = latestPredictionByRole(predictions, "predictive");
  const predictiveBlocked = predictivePrediction?.status === "blocked";
  const state = getGeneralState(telemetry);
  const agentView = translateAgentDecision(agentDecision);
  const reactiveFeatures = reactivePrediction?.features ?? [];
  const predictiveFeatures = predictivePrediction?.features ?? [];
  const broadcastBadge = liveBadge(telemetry);

  const activeEmbedUrl = session?.vdo_ninja?.embed_url;

  return (
    <div className="app-page app-page-wide">
      <PageHeader
        eyebrow="Monitoreo en tiempo real"
        title="Transmisión en vivo"
        description={session?.name || "Cargando detalles…"}
        action={<>
          <Button className="flex-1 sm:flex-none" variant={monitoring ? "outline" : "default"} onClick={() => setMonitoring(!monitoring)}>
            {monitoring ? <Pause className="mr-2 size-4" /> : <Play className="mr-2 size-4" />}
            {monitoring ? "Pausar monitoreo" : "Reanudar monitoreo"}
          </Button>
          <Button className="flex-1 sm:flex-none" variant="destructive" onClick={() => navigate("/history")}>
            <Square className="mr-2 size-4" />
            Salir del monitoreo
          </Button>
        </>}
      />

      {error ? <Alert variant="destructive"><AlertTitle>Error de conexión</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}
      {predictiveBlocked ? (
        <Alert className="border-warning/40 bg-warning/5 text-foreground">
          <AlertTriangle className="text-warning" />
          <AlertTitle>Modelo predictivo esperando historial suficiente</AlertTitle>
          <AlertDescription>{predictivePrediction?.reason || "La predicción de los próximos 10 minutos se activará cuando exista una ventana continua de datos válida."}</AlertDescription>
        </Alert>
      ) : null}
      
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: "Teléfono", value: phoneStatus ?? telemetry?.phone_status, icon: Smartphone },
          { label: "OBS", value: telemetry?.obs_status, icon: Monitor },
          { label: "MediaMTX", value: telemetry?.mediamtx_status, icon: Server },
        ].map((item) => (
          <div key={item.label} className="data-tile flex items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><item.icon className="size-5" /></div>
            <div className="min-w-0">
              <div className="text-xs font-medium text-muted-foreground">{item.label}</div>
              <div className="truncate text-sm font-semibold">{connectionLabel(item.value)}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,0.85fr)]">
        {/* Video Player */}
        <Card className="overflow-hidden border-primary/20 py-0">
          <CardHeader className="flex flex-col gap-3 border-b bg-muted/30 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <Badge variant={broadcastBadge.variant} className={broadcastBadge.pulse ? "animate-pulse" : undefined}>{broadcastBadge.label}</Badge>
              {session?.created_at && (
                <div className="flex min-w-0 items-center gap-1 text-sm text-muted-foreground">
                  <Clock className="size-4" />
                  <span>{new Date(session.created_at).toLocaleTimeString()}</span>
                </div>
              )}
            </div>
            
            <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:flex-wrap sm:justify-end">
              <ReplaceVideoLinkDialog onLinkUpdated={async (url) => {
                if (!sessionId) throw new Error("No se encontró la transmisión para actualizar.");
                const updated = await api.updateVideoLink(sessionId, url);
                setSession((current) => current ? {
                  ...current,
                  vdo_ninja: { ...(current.vdo_ninja ?? {}), embed_url: updated.embed_url, source: "external" },
                } : current);
              }} />
              
              <Button variant="outline" size="sm" onClick={() => setReconnectKey(k => k + 1)}>
                Reconectar video
              </Button>

              {activeEmbedUrl && (
                <Button variant="outline" size="sm" asChild>
                  <a href={activeEmbedUrl} target="_blank" rel="noopener noreferrer">
                    Abrir en nueva pestaña
                  </a>
                </Button>
              )}

              <Button variant="outline" size="sm" onClick={() => setHideVideo(!hideVideo)}>
                {hideVideo ? "Mostrar video" : "Ocultar video"}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="relative flex aspect-video min-h-56 items-center justify-center bg-media-background p-0">
            {hideVideo ? (
              <div className="text-muted-foreground flex flex-col items-center gap-2">
                <Activity className="size-8 opacity-50" />
                <span>Vista previa oculta temporalmente</span>
              </div>
            ) : (
              activeEmbedUrl ? (
                <VideoPreview key={reconnectKey} embedUrl={activeEmbedUrl} isLiveMonitor={true} onStatus={setPhoneStatus} />
              ) : (
                <MediaMtxPlayer key={reconnectKey} whepUrl={stream?.whep_url ?? stream?.webrtc_url} hlsUrl={stream?.hls_url} />
              )
            )}
          </CardContent>
        </Card>

        {/* Status & Recommendation */}
        <div className="grid min-w-0 gap-6 sm:grid-cols-2 xl:grid-cols-1">
          <Card className={`${state.color} border-none shadow-md`}>
            <CardContent className="pt-6 flex items-start gap-4">
              <state.icon className="size-10 opacity-80 mt-1" />
              <div>
                <div className="text-sm opacity-90 uppercase tracking-wider font-semibold mb-1">Estado de transmisión</div>
                <div className="text-3xl font-bold mb-2">{state.state}</div>
                <div className="text-sm opacity-90 leading-relaxed">{state.desc}</div>
              </div>
            </CardContent>
          </Card>

          <Card className="flex-1 border-2 border-primary/20">
            <CardHeader className="pb-3">
              <CardDescription className="flex justify-between items-center">
                <span>Decisión del agente</span>
                <Badge variant="outline" className={agentView.tone}>Automático</Badge>
              </CardDescription>
              <CardTitle className={`text-xl ${agentView.tone}`}>{agentView.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">{agentView.detail}</p>
              <div className="rounded-lg border bg-muted/20 p-3 text-xs text-muted-foreground">
                Esta es la acción final del agente. Los resultados independientes de cada modelo aparecen en la sección siguiente.
              </div>
            </CardContent>
            <CardFooter className="bg-muted/30 py-3 text-xs text-muted-foreground flex gap-2">
              <Info className="size-4 shrink-0" />
              Los cambios de perfil y de escena se envían al conector OBS autenticado.
            </CardFooter>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Resultados de Machine Learning</CardTitle>
          <CardDescription>Salidas independientes de los modelos; el agente las combina para decidir la acción final.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <ModelResultPanel role="reactive" prediction={reactivePrediction} />
          <ModelResultPanel role="predictive" prediction={predictivePrediction} />
        </CardContent>
      </Card>

      <div className="grid min-w-0 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Disponibilidad de telemetría</CardTitle>
            <CardDescription>Estado de los valores recibidos, sin estimaciones adicionales</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { label: "Bitrate de salida de OBS", available: telemetry?.bitrate_kbps != null },
              { label: "FPS de OBS", available: telemetry?.fps != null },
              { label: "Frames omitidos", available: telemetry?.dropped_frames != null },
              { label: "Métricas de red compatibles", available: telemetry?.packet_loss_percent != null || telemetry?.latency_ms != null },
              { label: "Capacidad de subida medida", available: telemetry?.connection_capacity_mbps != null },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between gap-4 rounded-xl border p-3">
                <span className="font-medium">{item.label}</span>
                <Badge variant={item.available ? "secondary" : "outline"}>{item.available ? "Disponible" : "No disponible"}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Indicadores visibles</CardTitle>
            <CardDescription>Valores enviados por OBS y las fuentes compatibles</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
              <div className="data-tile text-center">
                <div className="text-2xl font-bold">{metricNumber(telemetry?.bitrate_kbps, 0)}</div>
                <div className="text-xs text-muted-foreground mt-1">Bitrate de salida</div>
                <div className="mt-0.5 text-[10px] text-muted-foreground">kbps</div>
              </div>
              <div className="data-tile text-center">
                <div className="text-2xl font-bold">{metricNumber(telemetry?.fps, 1)}</div>
                <div className="text-xs text-muted-foreground mt-1">FPS</div>
              </div>
              <div className="data-tile text-center">
                <div className="text-2xl font-bold">{metricNumber(telemetry?.dropped_frames, 0)}</div>
                <div className="text-xs text-muted-foreground mt-1">Frames omitidos</div>
              </div>
              <div className="data-tile text-center">
                <div className={`text-2xl font-bold ${telemetry?.packet_loss_percent == null ? "text-muted-foreground" : ""}`}>
                  {telemetry?.packet_loss_percent == null ? "--" : `${telemetry.packet_loss_percent.toFixed(1)}%`}
                </div>
                <div className="text-xs text-muted-foreground mt-1">Pérdida de paquetes</div>
              </div>
              <div className="data-tile text-center">
                <div className="text-2xl font-bold">{metricNumber(telemetry?.latency_ms, 1)}</div>
                <div className="mt-1 text-xs text-muted-foreground">Latencia</div>
                <div className="mt-0.5 text-[10px] text-muted-foreground">ms</div>
              </div>
              <div className="data-tile text-center">
                <div className="truncate text-xl font-bold">{profileLabel(telemetry?.current_profile)}</div>
                <div className="mt-1 text-xs text-muted-foreground">Perfil actual</div>
              </div>
              <div className="data-tile text-center">
                <div className="text-2xl font-bold">{telemetry?.jitter_ms != null ? telemetry.jitter_ms.toFixed(1) : "--"}</div>
                <div className="mt-1 text-xs text-muted-foreground">Jitter</div>
                <div className="mt-0.5 text-[10px] text-muted-foreground">ms</div>
              </div>
              <div className="data-tile text-center">
                <div className="text-2xl font-bold">{telemetry?.upload_mbps != null ? telemetry.upload_mbps.toFixed(2) : "--"}</div>
                <div className="mt-1 text-xs text-muted-foreground">Subida medida</div>
                <div className="mt-0.5 text-[10px] text-muted-foreground">Mbps</div>
              </div>
              <div className="data-tile text-center">
                <div className="text-2xl font-bold">{telemetry?.connection_capacity_mbps != null ? telemetry.connection_capacity_mbps.toFixed(2) : "--"}</div>
                <div className="mt-1 text-xs text-muted-foreground">Capacidad usada por ML</div>
                <div className="mt-0.5 text-[10px] text-muted-foreground">Mbps</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Variables utilizadas por cada modelo</CardTitle>
          <CardDescription>Validación separada de las entradas reactiva y predictiva informadas por la API.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6 xl:grid-cols-2">
          {([
            { role: "reactive" as const, prediction: reactivePrediction, features: reactiveFeatures },
            { role: "predictive" as const, prediction: predictivePrediction, features: predictiveFeatures },
          ]).map(({ role, prediction, features }) => (
            <section key={role} className="min-w-0 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold">{modelRoleLabel(role)}</h3>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{modelStatusLabel(prediction?.status)}</Badge>
                  <Badge variant="outline">{prediction?.model_version ? `Versión ${prediction.model_version}` : "Versión no disponible"}</Badge>
                </div>
              </div>
              {features.length > 0 ? (
                <div className="grid gap-3">
                  {features.map((feature, index) => <FeatureState key={`${role}-${feature.name}-${index}`} feature={feature} />)}
                </div>
              ) : (
                <div className="empty-state-panel">La API todavía no informó las variables de este modelo.</div>
              )}
            </section>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
