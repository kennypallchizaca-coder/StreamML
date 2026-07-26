import { useEffect, useState } from "react";
import { api } from "../api";
import type { AuditEvent, AuditEventsResponse } from "../types";
import { Card, CardContent } from "../components/ui/card";
import { FileText, Search, ShieldCheck, ShieldAlert, AlertTriangle, Info, Loader2, ChevronRight, ChevronLeft } from "@/components/icons";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Button } from "../components/ui/button";
import PageHeader from "../components/PageHeader";

function getLevelFromOutcome(outcome: string) {
  const o = outcome.toLowerCase();
  if (["error", "rate_limited", "failure", "rejected"].includes(o)) return "error";
  if (["degraded", "blocked"].includes(o)) return "warning";
  if (["success", "created", "updated", "deleted"].includes(o)) return "success";
  return "info";
}

function getLevelIcon(level: string) {
  switch (level) {
    case "error": return <ShieldAlert className="size-4" />;
    case "warning": return <AlertTriangle className="size-4" />;
    case "success": return <ShieldCheck className="size-4" />;
    default: return <Info className="size-4" />;
  }
}

function getLevelColor(level: string) {
  switch (level) {
    case "error": return "text-destructive bg-destructive/10 border-destructive/20";
    case "warning": return "text-warning bg-warning/10 border-warning/20";
    case "success": return "text-success bg-success/10 border-success/20";
    default: return "text-info bg-info/10 border-info/20";
  }
}

function formatActionTitle(action: string) {
  return action.split(".").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(" ");
}

export default function LogsPage() {
  const [data, setData] = useState<AuditEventsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [levelFilter, setLevelFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(0);
  const limit = 50;

  useEffect(() => {
    let active = true;
    setLoading(true);
    
    // Si hay búsqueda por texto y está buscando en la UI, el backend puede buscar por "action"
    // Pero si el usuario escribe cosas varias, podríamos filtrar en frontend o mandar el action.
    // Usaremos el action parameter para la busqueda
    
    api.getAuditEvents({
      limit,
      offset: page * limit,
      level: levelFilter !== "all" ? levelFilter : undefined,
      action: searchQuery.length >= 3 ? searchQuery : undefined,
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
  }, [page, levelFilter, searchQuery]);

  // Manejo de búsqueda con pequeño debounce manual para no golpear la API por cada letra si fuera rápido,
  // pero como es onChange directo, requerirá enter o esperar (vamos a usar onBlur o boton, o dejarlo así para simplificar)
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
        title="Logs de Auditoría" 
        description="Registro detallado de los eventos, accesos y operaciones del sistema." 
      />

      <Card className="mb-6">
        <CardContent className="p-4 flex flex-col sm:flex-row gap-4 items-center justify-between">
          <div className="flex w-full sm:w-auto items-center gap-2">
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
              <Input 
                type="search" 
                placeholder="Buscar por acción (Enter)..." 
                className="pl-9 bg-background" 
                onKeyDown={handleSearch}
                onBlur={(e) => { setSearchQuery(e.target.value); setPage(0); }}
              />
            </div>
            <Select value={levelFilter} onValueChange={(v) => { setLevelFilter(v); setPage(0); }}>
              <SelectTrigger className="w-full sm:w-[180px] bg-background">
                <SelectValue placeholder="Severidad" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los niveles</SelectItem>
                <SelectItem value="info">Información</SelectItem>
                <SelectItem value="success">Éxito</SelectItem>
                <SelectItem value="warning">Advertencia</SelectItem>
                <SelectItem value="error">Error</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          <div className="text-sm text-muted-foreground flex items-center gap-2">
            {loading && <Loader2 className="size-4 animate-spin" />}
            {data ? `Mostrando ${data.items.length} de ${data.total} registros` : ""}
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive mb-6">
          {error}
        </div>
      )}

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-muted-foreground uppercase bg-muted/50 border-b">
              <tr>
                <th className="px-6 py-3 font-medium">Fecha y Hora</th>
                <th className="px-6 py-3 font-medium">Nivel</th>
                <th className="px-6 py-3 font-medium">Acción</th>
                <th className="px-6 py-3 font-medium">Resultado</th>
                <th className="px-6 py-3 font-medium">Detalles</th>
              </tr>
            </thead>
            <tbody>
              {loading && !data && (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center">
                      <Loader2 className="size-8 animate-spin text-primary/50 mb-4" />
                      <p>Cargando registros del sistema...</p>
                    </div>
                  </td>
                </tr>
              )}
              
              {!loading && data?.items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center">
                      <FileText className="size-10 mb-2 opacity-20" />
                      <p>No se encontraron registros que coincidan con los filtros.</p>
                    </div>
                  </td>
                </tr>
              )}

              {data?.items.map((log) => {
                const level = getLevelFromOutcome(log.outcome);
                return (
                  <tr key={log.id} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-col">
                        <span className="font-medium text-foreground">{new Date(log.created_at).toLocaleDateString()}</span>
                        <span className="text-xs text-muted-foreground">{new Date(log.created_at).toLocaleTimeString()}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant="outline" className={`gap-1.5 ${getLevelColor(level)}`}>
                        {getLevelIcon(level)}
                        {level.charAt(0).toUpperCase() + level.slice(1)}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="font-medium">{formatActionTitle(log.action)}</div>
                      <div className="text-xs text-muted-foreground font-mono mt-0.5">{log.action}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-muted-foreground">{log.outcome}</span>
                    </td>
                    <td className="px-6 py-4 min-w-[250px]">
                      <div className="text-xs text-muted-foreground bg-muted/30 p-2 rounded border font-mono break-all line-clamp-2" title={JSON.stringify(log.details, null, 2)}>
                        {Object.keys(log.details || {}).length > 0 
                          ? JSON.stringify(log.details).replace(/["{}]/g, '').substring(0, 100) + (JSON.stringify(log.details).length > 100 ? '...' : '')
                          : 'Sin detalles adicionales'
                        }
                      </div>
                      {log.client_ip && (
                        <div className="text-[10px] text-muted-foreground mt-1">IP: {log.client_ip}</div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        
        {data && data.total > limit && (
          <div className="p-4 border-t flex items-center justify-between bg-muted/10">
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
          </div>
        )}
      </Card>
    </div>
  );
}
