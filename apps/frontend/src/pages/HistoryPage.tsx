import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, normalizeSessions } from "../api";
import { Badge } from "../components/ui/badge";
import type { StreamSession } from "../types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Search, ArrowLeft, Video, Activity, Clock, CheckCircle2, AlertTriangle } from "@/components/icons";
import { Input } from "../components/ui/input";
import PageHeader from "../components/PageHeader";
import { isSessionLive, needsQualityAttention, sessionStateLabel } from "../lib/sessionPresentation";

// Helper to translate final internal prediction
function translateFinalQuality(rec?: string | null) {
  if (!rec) return { text: "No disponible", color: "text-muted-foreground", conclusion: "La sesión no tiene una recomendación de modelo registrada." };
  if (rec === "high") return { text: "Perfil alto", color: "text-success", conclusion: "La última inferencia reactiva recomendó el perfil alto." };
  if (rec === "medium") return { text: "Perfil medio", color: "text-info", conclusion: "La última inferencia reactiva recomendó el perfil medio." };
  if (rec === "low") return { text: "Perfil básico", color: "text-warning", conclusion: "La última inferencia reactiva recomendó reducir al perfil básico." };
  if (rec === "maintain") return { text: "Mantener", color: "text-success", conclusion: "La última inferencia predictiva indicó que el perfil actual podía mantenerse." };
  if (rec === "downgrade_needed" || rec === "downgrade") return { text: "Reducir calidad", color: "text-warning", conclusion: "La última inferencia predictiva anticipó que era necesario reducir la calidad." };
  return { text: rec, color: "text-muted-foreground", conclusion: `La API informó la recomendación ${rec}.` };
}

export default function HistoryPage() {
  const [sessions, setSessions] = useState<StreamSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedSession, setSelectedSession] = useState<StreamSession | null>(null);
  
  useEffect(() => {
    let active = true;
    void api.listSessions().then((result) => { 
      if (active) setSessions(normalizeSessions(result)); 
    }).catch((reason) => { 
      if (active) setError(reason instanceof Error ? reason.message : "No pudimos cargar tu historial."); 
    });
    return () => { active = false; };
  }, []);

  const filteredSessions = sessions?.filter(s => 
    (s.name || "").toLowerCase().includes(searchTerm.toLowerCase()) || 
    new Date(s.created_at || "").toLocaleDateString().includes(searchTerm)
  );

  if (selectedSession) {
    const quality = translateFinalQuality(selectedSession.latest_prediction?.recommendation);
    
    let durationStr = "--";
    if (selectedSession.created_at && selectedSession.updated_at) {
      const diffMs = new Date(selectedSession.updated_at).getTime() - new Date(selectedSession.created_at).getTime();
      if (diffMs > 0) {
        const h = Math.floor(diffMs / 3600000);
        const m = Math.floor((diffMs % 3600000) / 60000);
        durationStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
      }
    }

    const requiresAttention = needsQualityAttention(selectedSession.latest_prediction?.recommendation);
    const conclusionIcon = requiresAttention
      ? <AlertTriangle className="size-6 text-warning shrink-0 mt-0.5" />
      : selectedSession.latest_prediction
        ? <CheckCircle2 className="size-6 text-success shrink-0 mt-0.5" />
        : <Activity className="size-6 text-muted-foreground shrink-0 mt-0.5" />;

    return (
      <div className="app-page max-w-5xl">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-2">
          <div>
            <Button variant="ghost" size="sm" onClick={() => setSelectedSession(null)} className="-ml-3 mb-2 text-muted-foreground">
              <ArrowLeft className="mr-2 size-4" />
              Volver al historial
            </Button>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{selectedSession.name || "Transmisión sin nombre"}</h2>
            <p className="text-muted-foreground mt-1">{new Date(selectedSession.created_at || "").toLocaleString()}</p>
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-1">Duración (estimada)</div>
              <div className="text-2xl font-bold flex items-center gap-2">
                <Clock className="size-5 text-primary" />
                {durationStr}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-1">Calidad general</div>
              <div className="text-2xl font-bold flex items-center gap-2">
                <Activity className="size-5 text-primary" />
                <span className={quality.color}>{quality.text}</span>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Conclusión</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="p-4 rounded-xl bg-muted/30 border border-muted flex items-start gap-4">
              {conclusionIcon}
              <div>
                <p className="font-medium text-foreground">{quality.conclusion}</p>
                <p className="mt-1 text-sm text-muted-foreground">Este resumen corresponde a la última inferencia disponible, no a una estimación de toda la sesión.</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="app-page app-page-wide">
      <PageHeader eyebrow="Sesiones" title="Historial" description="Revisa el rendimiento y los informes de tus transmisiones anteriores." />
      
      {error ? <Alert variant="destructive"><AlertTitle>Error</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}
      
      <Card>
        <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <CardTitle>Registro de sesiones</CardTitle>
            <CardDescription>Todas las transmisiones realizadas en tu cuenta.</CardDescription>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:w-64">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="search"
                placeholder="Buscar transmisión..."
                className="pl-8"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {sessions === null && !error ? <div className="text-center py-8 text-muted-foreground">Cargando tu historial...</div> : null}
          
          {sessions?.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center px-4">
              <Video className="size-12 text-muted-foreground opacity-30 mb-4" />
              <h3 className="text-lg font-semibold">No hay sesiones almacenadas</h3>
              <p className="text-muted-foreground text-sm mt-1 max-w-sm">Cuando inicies y finalices transmisiones, aparecerán aquí para que puedas analizar su rendimiento.</p>
            </div>
          ) : null}
          
          {filteredSessions?.length ? (
            <div className="overflow-x-auto rounded-xl border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Transmisión</TableHead>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Duración</TableHead>
                    <TableHead>Calidad general</TableHead>
                    <TableHead>Alertas</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredSessions.map((session) => {
                    const quality = translateFinalQuality(session.latest_prediction?.recommendation);
                    const isActive = isSessionLive(session.status);
                    const recommendation = session.latest_prediction?.recommendation;
                    const alertCount = recommendation ? (needsQualityAttention(recommendation) ? "1" : "0") : "--";
                    
                    let durationStr = "--";
                    if (session.created_at && session.updated_at) {
                      const diffMs = new Date(session.updated_at).getTime() - new Date(session.created_at).getTime();
                      if (diffMs > 0) {
                        const h = Math.floor(diffMs / 3600000);
                        const m = Math.floor((diffMs % 3600000) / 60000);
                        durationStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
                      }
                    }

                    return (
                      <TableRow key={session.id} className="cursor-pointer hover:bg-muted/5" onClick={() => !isActive && setSelectedSession(session)}>
                        <TableCell>
                          <div className="font-medium text-foreground">{session.name || "Sin nombre"}</div>
                        </TableCell>
                        <TableCell className="text-sm">
                          {session.created_at ? new Date(session.created_at).toLocaleDateString() : "--"}
                        </TableCell>
                        <TableCell className="text-sm">
                          {isActive ? "--" : durationStr}
                        </TableCell>
                        <TableCell>
                          {isActive ? (
                            <Badge variant="default" className="bg-success text-success-foreground hover:bg-success/90">{sessionStateLabel(session.status)}</Badge>
                          ) : (
                            <Badge variant="outline" className={quality.color + " border-current/20 bg-current/10"}>{quality.text}</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {isActive ? "--" : alertCount}
                        </TableCell>
                        <TableCell className="text-right">
                          {isActive ? (
                            <Button variant="outline" size="sm" asChild onClick={(e) => e.stopPropagation()}>
                              <Link to={`/sessions/${encodeURIComponent(session.id)}/live`}>
                                Monitorear
                              </Link>
                            </Button>
                          ) : (
                            <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); setSelectedSession(session); }}>
                              Ver detalles
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : (
            sessions?.length && filteredSessions?.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">No se encontraron transmisiones que coincidan con tu búsqueda.</div>
            ) : null
          )}
        </CardContent>
      </Card>
    </div>
  );
}
