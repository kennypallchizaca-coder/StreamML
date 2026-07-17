import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, normalizeSessions } from "../api";
import { Badge } from "../components/ui/badge";
import type { StreamSession } from "../types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Search, Filter, Download, ArrowLeft, Video, Activity, Clock, Bell, CheckCircle2, AlertTriangle } from "lucide-react";
import { Input } from "../components/ui/input";
import PageHeader from "../components/PageHeader";

// Helper to translate final internal prediction
function translateFinalQuality(rec?: string | null) {
  if (!rec) return { text: "No disponible", color: "text-muted-foreground" };
  if (rec === "high" || rec === "maintain") return { text: "Excelente", color: "text-green-500" };
  if (rec === "medium") return { text: "Buena", color: "text-blue-500" };
  return { text: "Inestable", color: "text-amber-500" };
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

    let conclusionText = "No hay suficientes datos para generar una conclusión.";
    let conclusionIcon = <Activity className="size-6 text-muted-foreground shrink-0 mt-0.5" />;
    
    if (quality.text === "Excelente" || quality.text === "Buena") {
      conclusionText = "La transmisión mantuvo una buena estabilidad durante la mayor parte de la sesión.";
      conclusionIcon = <CheckCircle2 className="size-6 text-green-500 shrink-0 mt-0.5" />;
    } else if (quality.text === "Inestable") {
      conclusionText = "Se registraron variaciones de calidad que podrían haber afectado a los espectadores.";
      conclusionIcon = <AlertTriangle className="size-6 text-amber-500 shrink-0 mt-0.5" />;
    }

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
                <p className="font-medium text-foreground">{conclusionText}</p>
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
            <Button variant="outline" size="icon">
              <Filter className="h-4 w-4" />
            </Button>
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
                    const isActive = ["active", "live", "streaming"].includes(session.status?.toLowerCase() ?? "");
                    
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
                            <Badge variant="default" className="bg-green-500 hover:bg-green-600">En vivo</Badge>
                          ) : (
                            <Badge variant="outline" className={quality.color + " border-current/20 bg-current/10"}>{quality.text}</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {isActive ? "--" : "Ninguna"}
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

function AlertTriangleIcon(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  )
}
