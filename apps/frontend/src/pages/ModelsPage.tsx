import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import StatusBadge from "../components/StatusBadge";
import type { ModelSummary, ModelsResponse } from "../types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Cpu } from "@/components/icons";
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import PageHeader from "../components/PageHeader";

function normalizeModels(value: ModelsResponse | ModelSummary[]): ModelSummary[] {
  if (Array.isArray(value)) return value;
  if (value.items) return value.items;
  if (value.models) return value.models;
  return [value.reactive, value.predictive].filter((item): item is ModelSummary => Boolean(item));
}

function primitiveMetrics(metrics?: Record<string, unknown>): Array<[string, string]> {
  if (!metrics) return [];
  const rows: Array<[string, string]> = [];
  function visit(value: unknown, path: string) {
    if (typeof value === "number" && Number.isFinite(value)) rows.push([path, String(value)]);
    else if (typeof value === "string" || typeof value === "boolean") rows.push([path, String(value)]);
    else if (value && typeof value === "object" && !Array.isArray(value)) {
      for (const [key, child] of Object.entries(value as Record<string, unknown>)) visit(child, path ? `${path}.${key}` : key);
    }
  }
  visit(metrics, "");
  return rows;
}

export default function ModelsPage() {
  const [models, setModels] = useState<ModelSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    let active = true;
    void api.getModels().then((value) => { 
      if (active) setModels(normalizeModels(value)); 
    }).catch((reason) => { 
      if (active) setError(reason instanceof Error ? reason.message : "No fue posible cargar los modelos."); 
    });
    return () => { active = false; };
  }, []);
  
  const hasModels = useMemo(() => Boolean(models?.length), [models]);

  return (
    <div className="app-page app-page-wide">
      <PageHeader eyebrow="Registro oficial" title="Modelos y métricas" description="Información leída directamente desde el registro oficial expuesto por la API." />
      
      {error ? <Alert variant="destructive"><AlertTitle>Error</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}
      {models === null && !error ? <div className="text-center py-8 text-muted-foreground">Cargando modelos…</div> : null}
      {!hasModels && models !== null ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-10 text-center">
            <Cpu className="size-10 text-muted-foreground mb-4" />
            <div className="text-lg font-semibold">No hay metadata disponible</div>
            <p className="text-sm text-muted-foreground">La API no devolvió modelos oficiales.</p>
          </CardContent>
        </Card>
      ) : null}
      
      <div className="grid min-w-0 gap-6 xl:grid-cols-2">
        {models?.map((model, index) => {
          const metrics = primitiveMetrics(model.metrics);
          return (
            <Card key={`${model.role ?? model.name ?? "model"}-${index}`} className="flex flex-col">
              <CardHeader className="flex flex-row items-start justify-between pb-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Cpu className="size-5 text-primary" />
                    <CardDescription>{model.role ?? "Modelo"}</CardDescription>
                  </div>
                  <CardTitle className="text-xl">{model.name ?? model.algorithm ?? "Nombre no disponible"}</CardTitle>
                </div>
                <StatusBadge value={model.status} />
              </CardHeader>
              <CardContent className="flex-1 flex flex-col gap-6">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="flex flex-col">
                    <span className="text-muted-foreground">Algoritmo</span>
                    <span className="font-medium">{model.algorithm ?? "No disponible"}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-muted-foreground">Versión</span>
                    <span className="font-medium">{model.version ?? "No disponible"}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-muted-foreground">Threshold</span>
                    <span className="font-medium">{model.threshold ?? "No disponible"}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-muted-foreground">Clases</span>
                    <span className="font-medium">{model.classes?.join(", ") || "No disponible"}</span>
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-semibold mb-3">Features oficiales</h3>
                  {model.features?.length ? (
                    <div className="flex flex-wrap gap-2">
                      {model.features.map((feature) => (
                        <Badge key={feature} variant="secondary">{feature}</Badge>
                      ))}
                    </div>
                  ) : (
                    <span className="text-sm text-muted-foreground">No disponible</span>
                  )}
                </div>

                <div>
                  <h3 className="text-sm font-semibold mb-3">Métricas publicadas</h3>
                  {metrics.length ? (
                    <div className="max-h-80 overflow-auto rounded-xl border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Métrica</TableHead>
                            <TableHead className="text-right">Valor</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {metrics.map(([name, value]) => (
                            <TableRow key={name}>
                              <TableCell className="font-medium text-xs">{name}</TableCell>
                              <TableCell className="text-right text-xs">{value}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <span className="text-sm text-muted-foreground">No disponible</span>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
