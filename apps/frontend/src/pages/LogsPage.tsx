import { useEffect, useState } from "react";
import { api } from "../api";
import type { AuditEvent, AuditEventsResponse } from "../types";
import { Card, CardContent } from "../components/ui/card";
import { FileText, Search, ShieldCheck, ShieldAlert, AlertTriangle, Info, Loader2, ChevronRight, ChevronLeft, History as CalendarIcon } from "@/components/icons";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Button } from "../components/ui/button";
import PageHeader from "../components/PageHeader";

interface MappedLog {
  raw: AuditEvent;
  datetime: string;
  process: string;
  action: string;
  decision: string;
  reason: string;
  state: string;
  priority: "Alto" | "Medio" | "Bajo";
  result: string;
  error?: string;
}

function mapLog(log: AuditEvent): MappedLog {
  const dt = new Date(log.created_at);
  const datetime = `${dt.toLocaleDateString()} ${dt.toLocaleTimeString()}`;
  
  let process = "Sistema";
  let action = log.action;
  let decision = "Ninguna";
  let reason = "N/A";
  let state = "Completado";
  let priority: "Alto" | "Medio" | "Bajo" = "Bajo";
  let result = log.outcome;
  let error = undefined;

  // 1. Map outcomes
  const o = log.outcome.toLowerCase();
  if (["error", "failure", "rejected"].includes(o)) {
    priority = "Alto";
    state = "Error";
    error = (log.details?.error as string) || "Fallo en la operación";
    result = "Operación fallida";
  } else if (["warning", "rate_limited", "degraded", "blocked"].includes(o)) {
    priority = "Medio";
    state = "Advertencia";
    result = "Operación con advertencias";
    if (o === "blocked") {
       result = "Acción bloqueada temporalmente";
    }
  } else {
    priority = "Bajo";
    state = "Completado";
    result = "Operación exitosa";
  }

  // 2. Map Processes & specific actions
  if (log.action.startsWith("agent.")) {
    process = "Monitoreo de transmisión";
    action = "Aplicación de una decisión automática";
    
    if (log.action === "agent.decision.reduce") {
        decision = "Reducir temporalmente la resolución del video";
        result = "Resolución reducida correctamente";
        priority = "Alto";
    } else if (log.action === "agent.decision.increase") {
        decision = "Subir la resolución del video";
        result = "Resolución aumentada correctamente";
        priority = "Medio";
    } else if (log.action === "agent.decision.switch_to_backup") {
        action = "Pérdida de conexión detectada";
        decision = "Activar video de respaldo";
        result = "Respaldo activado correctamente";
        priority = "Alto";
    } else if (log.action === "agent.decision.restore_live") {
        action = "Recuperación de la transmisión";
        decision = "Restaurar en vivo";
        result = "Transmisión en vivo restaurada";
        priority = "Medio";
    } else if (log.action === "agent.status") {
        action = "Ejecución de una predicción";
        decision = "Ninguna";
        result = "Predicción ejecutada";
    }
    
    if (log.details?.reason) {
        reason = log.details.reason as string;
    } else {
        reason = "Evitar interrupciones y mantener estable la transmisión.";
    }
    
    // States for agent decisions
    if (["error", "warning", "blocked"].includes(o)) {
       state = o === "blocked" ? "Analizando datos" : (state === "Error" ? "Error" : "Advertencia");
    } else {
       state = "Tomando una decisión";
    }
    
  } else if (log.action.startsWith("telemetry.")) {
    process = "Recopilación de Telemetría";
    action = "Detección de caída de datos / Recepción";
    decision = "Almacenar métricas de red";
    reason = "Ingesta periódica";
    if (log.outcome === "success") {
       result = "Datos recopilados correctamente";
    }
  } else if (log.action.startsWith("auth.")) {
    process = "Autenticación";
    if (log.action === "auth.login") {
       action = "Inicio de sesión de usuario";
       decision = "Conceder acceso";
       reason = "Validación de credenciales";
       if (log.outcome === "success") result = "Sesión iniciada correctamente";
    } else {
       action = "Verificación de sesión";
       reason = "Validación de token";
    }
  } else if (log.action.startsWith("connector.")) {
    process = "Conexión con el Sistema Local";
    action = "Establecimiento de puente";
    reason = "Asegurar que el cliente local esté activo";
  }

  // Fallback reason if empty
  if (!reason || reason === "N/A") {
    if (log.details && Object.keys(log.details).length > 0) {
      reason = JSON.stringify(log.details).replace(/["{}]/g, '').substring(0, 100);
    } else {
      reason = "Mantenimiento interno del sistema";
    }
  }

  return { raw: log, datetime, process, action, decision, reason, state, priority, result, error };
}

function PriorityBadge({ priority }: { priority: string }) {
  if (priority === "Alto") return <Badge variant="outline" className="gap-1.5 text-destructive bg-destructive/10 border-destructive/20"><ShieldAlert className="size-3" /> Alto</Badge>;
  if (priority === "Medio") return <Badge variant="outline" className="gap-1.5 text-warning bg-warning/10 border-warning/20"><AlertTriangle className="size-3" /> Medio</Badge>;
  return <Badge variant="outline" className="gap-1.5 text-info bg-info/10 border-info/20"><Info className="size-3" /> Bajo</Badge>;
}

export default function LogsPage() {
  const [data, setData] = useState<AuditEventsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [levelFilter, setLevelFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [processFilter, setProcessFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(0);
  const limit = 50;

  useEffect(() => {
    let active = true;
    setLoading(true);
    
    let actionParam: string | undefined = undefined;
    if (processFilter !== "all") {
       actionParam = processFilter;
    } else if (searchQuery.length >= 3) {
       actionParam = searchQuery;
    }
    
    api.getAuditEvents({
      limit,
      offset: page * limit,
      level: levelFilter !== "all" ? levelFilter : undefined,
      action: actionParam,
      date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
      date_to: dateTo ? new Date(dateTo).toISOString() : undefined,
    }).then((res) => {
      if (active) {
        setData(res);
        setError(null);
      }
    }).catch((err) => {
      if (active) {
        setError(err.message || "Error al cargar los logs.");
        setData(null);
      }
    }).finally(() => {
      if (active) setLoading(false);
    });

    return () => { active = false; };
  }, [page, levelFilter, searchQuery, processFilter, dateFrom, dateTo]);

  const handleSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      setSearchQuery(e.currentTarget.value);
      setPage(0);
    }
  };

  return (
    <div className="app-page max-w-7xl">
      <PageHeader 
        eyebrow="Sistema" 
        title="Logs y Auditoría de Decisiones" 
        description="Explora las acciones, decisiones y monitoreo del sistema predictivo de manera detallada." 
      />

      <Card className="mb-6">
        <CardContent className="p-4 flex flex-col gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4">
            <div className="relative md:col-span-1">
              <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
              <Input 
                type="search" 
                placeholder="Buscar por texto..." 
                className="pl-9 bg-background" 
                onKeyDown={handleSearch}
                onBlur={(e) => { setSearchQuery(e.target.value); setPage(0); }}
              />
            </div>
            <Select value={processFilter} onValueChange={(v) => { setProcessFilter(v); setPage(0); }}>
              <SelectTrigger className="bg-background">
                <SelectValue placeholder="Proceso" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los procesos</SelectItem>
                <SelectItem value="agent">Modelo Predictivo</SelectItem>
                <SelectItem value="telemetry">Telemetría y Red</SelectItem>
                <SelectItem value="auth">Autenticación</SelectItem>
                <SelectItem value="connector">Conector Local</SelectItem>
              </SelectContent>
            </Select>
            <Select value={levelFilter} onValueChange={(v) => { setLevelFilter(v); setPage(0); }}>
              <SelectTrigger className="bg-background">
                <SelectValue placeholder="Nivel" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los niveles</SelectItem>
                <SelectItem value="error">Nivel Alto (Errores)</SelectItem>
                <SelectItem value="warning">Nivel Medio (Advs)</SelectItem>
                <SelectItem value="success">Nivel Bajo (Éxitos)</SelectItem>
                <SelectItem value="info">Info</SelectItem>
              </SelectContent>
            </Select>
            <div className="flex gap-2 md:col-span-2">
              <div className="relative flex-1">
                <Input type="date" className="bg-background" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setPage(0); }} />
              </div>
              <div className="relative flex-1">
                <Input type="date" className="bg-background" value={dateTo} onChange={e => { setDateTo(e.target.value); setPage(0); }} />
              </div>
            </div>
          </div>
          
          <div className="text-sm text-muted-foreground flex items-center justify-between">
            <div className="flex items-center gap-2">
               {loading && <Loader2 className="size-4 animate-spin" />}
               {data ? `Mostrando ${data.items.length} de ${data.total} registros` : ""}
            </div>
            {(dateFrom || dateTo) && (
              <Button variant="secondary" size="sm" onClick={() => { setDateFrom(""); setDateTo(""); setPage(0); }}>
                Limpiar fechas
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive mb-6">
          {error}
        </div>
      )}

      <div className="space-y-4">
          {loading && !data && (
            <Card>
              <CardContent className="p-10 text-center text-muted-foreground">
                <div className="flex flex-col items-center justify-center">
                  <Loader2 className="size-8 animate-spin text-primary/50 mb-4" />
                  <p>Cargando el registro de procesos y decisiones...</p>
                </div>
              </CardContent>
            </Card>
          )}
          
          {!loading && data?.items.length === 0 && (
            <Card>
              <CardContent className="p-10 text-center text-muted-foreground">
                <div className="flex flex-col items-center justify-center">
                  <FileText className="size-10 mb-2 opacity-20" />
                  <p>No se encontraron procesos ni decisiones con estos filtros.</p>
                </div>
              </CardContent>
            </Card>
          )}

          {data?.items.map((rawLog) => {
            const log = mapLog(rawLog);
            return (
              <Card key={log.raw.id} className="overflow-hidden transition-all hover:border-primary/30">
                <CardContent className="p-0">
                  <div className="bg-muted/30 p-4 border-b flex flex-wrap gap-4 items-center justify-between">
                     <div className="flex items-center gap-3">
                       <PriorityBadge priority={log.priority} />
                       <div className="font-semibold text-base">{log.process}</div>
                     </div>
                     <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <CalendarIcon className="size-4" />
                        {log.datetime}
                     </div>
                  </div>
                  <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 text-sm">
                     <div className="space-y-1">
                        <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Estado Actual</span>
                        <div className="font-medium flex items-center gap-2">
                           <div className={`size-2 rounded-full ${log.state === 'Error' ? 'bg-destructive' : log.state === 'Advertencia' ? 'bg-warning' : 'bg-success'}`}></div>
                           {log.state}
                        </div>
                     </div>
                     <div className="space-y-1">
                        <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Acción Realizada</span>
                        <div className="font-medium text-foreground">{log.action}</div>
                     </div>
                     <div className="space-y-1">
                        <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Decisión Tomada</span>
                        <div className="font-medium text-foreground">{log.decision}</div>
                     </div>
                     <div className="space-y-1 md:col-span-2 lg:col-span-3">
                        <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Motivo de la decisión</span>
                        <div className="bg-muted/20 p-2 rounded text-foreground">{log.reason}</div>
                     </div>
                     <div className="space-y-1 md:col-span-2 lg:col-span-3">
                        <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Resultado del proceso</span>
                        <div className="font-medium text-foreground flex items-center gap-2">
                            {log.error ? <ShieldAlert className="size-4 text-destructive" /> : <ShieldCheck className="size-4 text-success" />}
                            {log.result}
                        </div>
                     </div>
                     {log.error && (
                        <div className="space-y-1 md:col-span-2 lg:col-span-3 bg-destructive/10 border border-destructive/20 p-3 rounded text-destructive">
                           <span className="font-medium text-xs uppercase tracking-wider block mb-1">Mensaje de Error</span>
                           <div>{log.error}</div>
                        </div>
                     )}
                  </div>
                </CardContent>
              </Card>
            );
          })}

          {data && data.total > limit && (
            <Card>
                <CardContent className="p-4 flex items-center justify-between bg-muted/10">
                <span className="text-sm text-muted-foreground">
                    Página {page + 1} de {Math.ceil(data.total / limit)}
                </span>
                <div className="flex gap-2">
                    <Button 
                    variant="outline" 
                    size="sm" 
                    disabled={page === 0} 
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    >
                    <ChevronLeft className="size-4 mr-1" /> Anterior
                    </Button>
                    <Button 
                    variant="outline" 
                    size="sm" 
                    disabled={(page + 1) * limit >= data.total} 
                    onClick={() => setPage(p => p + 1)}
                    >
                    Siguiente <ChevronRight className="size-4 ml-1" />
                    </Button>
                </div>
                </CardContent>
            </Card>
          )}
      </div>
    </div>
  );
}
