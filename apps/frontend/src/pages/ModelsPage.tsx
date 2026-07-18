import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import StatusBadge from "../components/StatusBadge";
import type { ModelMetricSummary, ModelSummary, ModelsResponse } from "../types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Activity, AlertTriangle, CheckCircle2, Cpu } from "@/components/icons";
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import PageHeader from "../components/PageHeader";

function normalizeModels(value: ModelsResponse | ModelSummary[]): ModelSummary[] {
  if (Array.isArray(value)) return value;
  if (value.items) return value.items;
  if (value.models) return value.models;
  return [value.reactive, value.predictive].filter((item): item is ModelSummary => Boolean(item));
}

function percent(value?: number | null, digits = 1) {
  return value == null || !Number.isFinite(value) ? "--" : `${(value * 100).toFixed(digits)}%`;
}

function roleLabel(role?: string) {
  return role === "predictive" ? "Modelo predictivo" : role === "reactive" ? "Modelo reactivo" : "Modelo ML";
}

function datasetValue(dataset: Record<string, unknown> | null | undefined, key: string) {
  const value = dataset?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function classDistribution(dataset?: Record<string, unknown> | null): Array<[string, number]> {
  const raw = dataset?.class_distribution;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
  return Object.entries(raw as Record<string, unknown>)
    .map(([label, value]) => [label, typeof value === "number" ? value : 0] as [string, number])
    .filter(([, count]) => count >= 0);
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="data-tile">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
    </div>
  );
}

function ConfusionMatrix({ metrics, classes }: { metrics?: ModelMetricSummary | null; classes: string[] }) {
  const matrix = metrics?.confusion_matrix;
  if (!matrix?.length || matrix.length !== classes.length) {
    return <p className="text-sm text-muted-foreground">Matriz no disponible.</p>;
  }
  return (
    <div className="overflow-x-auto border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Real ↓ / Predicción →</TableHead>
            {classes.map((label) => <TableHead key={label} className="text-center">{label}</TableHead>)}
          </TableRow>
        </TableHeader>
        <TableBody>
          {matrix.map((row, rowIndex) => (
            <TableRow key={classes[rowIndex]}>
              <TableCell className="font-medium">{classes[rowIndex]}</TableCell>
              {row.map((value, columnIndex) => (
                <TableCell
                  key={`${rowIndex}-${columnIndex}`}
                  className={rowIndex === columnIndex ? "bg-success/10 text-center font-semibold text-success" : "text-center tabular-nums"}
                >
                  {value}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ModelEvidence({ model }: { model: ModelSummary }) {
  const test = model.test;
  const baseline = model.baseline?.test;
  const comparison = Object.entries(model.model_comparison ?? {});
  const importance = model.feature_importance ?? [];
  const maxImportance = Math.max(...importance.map((item) => Math.abs(item.importance)), 0.0001);
  const rows = datasetValue(model.dataset, "rows");
  const windows = datasetValue(model.dataset, "windows");
  const sessions = datasetValue(model.dataset, "sessions");
  const distribution = classDistribution(model.dataset);
  const totalClasses = Math.max(1, distribution.reduce((sum, [, count]) => sum + count, 0));
  const classes = model.classes ?? [];

  return (
    <Card className="model-evidence overflow-hidden">
      <CardHeader className="flex flex-col gap-4 border-b bg-muted/20 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-agent">
            <Cpu className="size-5" />
            <span className="text-xs font-semibold uppercase tracking-[0.14em]">{roleLabel(model.role)}</span>
          </div>
          <CardTitle className="text-2xl">{model.algorithm ?? "Algoritmo no disponible"}</CardTitle>
          <CardDescription>
            Versión {model.version ?? "--"}
            {model.threshold != null ? ` · threshold ${model.threshold}` : ""}
            {model.trained_at ? ` · entrenado ${new Date(model.trained_at).toLocaleDateString("es-EC")}` : ""}
          </CardDescription>
        </div>
        <StatusBadge value={model.status} />
      </CardHeader>

      <CardContent className="space-y-7">
        <section aria-label={`Evidencia de ${roleLabel(model.role)}`}>
          <div className="section-heading mb-3">
            <div>
              <h3>Evidencia de generalización</h3>
            </div>
            {model.official_release ? <Badge variant="secondary"><CheckCircle2 />Artefacto oficial</Badge> : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile label="Macro F1" value={percent(test?.macro_f1)} />
            <MetricTile label="Accuracy balanceada" value={percent(test?.balanced_accuracy)} />
            <MetricTile label="Baseline" value={percent(baseline?.macro_f1)} />
            <MetricTile label="Mejora" value={percent(model.improvement_over_baseline_macro_f1)} />
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(17rem,0.8fr)]">
          <section>
            <h3 className="mb-3 text-sm font-semibold">Matriz de confusión</h3>
            <ConfusionMatrix metrics={test} classes={classes} />
          </section>
          <section>
            <h3 className="mb-3 text-sm font-semibold">Dataset y separación</h3>
            <div className="grid gap-2 text-sm">
              <div className="flex justify-between border-b py-2"><span className="text-muted-foreground">Sesiones</span><strong>{sessions ?? "--"}</strong></div>
              <div className="flex justify-between border-b py-2"><span className="text-muted-foreground">{windows != null ? "Ventanas" : "Filas"}</span><strong>{windows ?? rows ?? "--"}</strong></div>
              <div className="flex justify-between border-b py-2"><span className="text-muted-foreground">Brecha validación/prueba</span><strong>{percent(model.generalization_gap)}</strong></div>
              {model.lookback_seconds ? <div className="flex justify-between border-b py-2"><span className="text-muted-foreground">Historial</span><strong>{model.lookback_seconds / 60} min</strong></div> : null}
              {model.future_horizon_seconds ? <div className="flex justify-between border-b py-2"><span className="text-muted-foreground">Horizonte</span><strong>{model.future_horizon_seconds / 60} min</strong></div> : null}
            </div>
            {distribution.length ? (
              <div className="mt-4 space-y-2">
                {distribution.map(([label, count]) => (
                  <div key={label}>
                    <div className="mb-1 flex justify-between text-xs"><span>{label}</span><span>{count} · {percent(count / totalClasses)}</span></div>
                    <div className="h-1.5 bg-muted"><div className="h-full bg-primary" style={{ width: `${(count / totalClasses) * 100}%` }} /></div>
                  </div>
                ))}
              </div>
            ) : null}
          </section>
        </div>

        <details className="disclosure-card">
          <summary>
            <span><strong>Detalles técnicos</strong><small>Candidatos, importancia de variables y contrato oficial.</small></span>
          </summary>
          <div className="space-y-6 border-t p-5">
            {comparison.length ? (
              <section>
                <h3 className="mb-1 text-sm font-semibold">Comparación de candidatos</h3>
                <p className="mb-3 text-xs text-muted-foreground">La selección se realizó con validación; el conjunto de prueba permaneció reservado.</p>
                <div className="overflow-x-auto border">
                  <Table>
                    <TableHeader><TableRow><TableHead>Modelo</TableHead><TableHead>Macro F1 validación</TableHead><TableHead>Accuracy balanceada</TableHead><TableHead>Estado</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {comparison.map(([name, result]) => (
                        <TableRow key={name}>
                          <TableCell className="font-medium">{name}</TableCell>
                          <TableCell>{percent(result.validation?.macro_f1)}</TableCell>
                          <TableCell>{percent(result.validation?.balanced_accuracy)}</TableCell>
                          <TableCell>{name === model.algorithm ? <Badge variant="secondary">Seleccionado</Badge> : <span className="text-xs text-muted-foreground">Candidato</span>}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </section>
            ) : null}

            {importance.length ? (
              <section>
                <h3 className="mb-1 text-sm font-semibold">Variables con mayor influencia</h3>
                <p className="mb-3 text-xs text-muted-foreground">Magnitud informada por el modelo oficial; no implica causalidad.</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {importance.map((item) => (
                    <div key={item.feature} className="border p-3">
                      <div className="flex justify-between gap-3 text-xs"><span className="truncate font-medium">{item.feature}</span><span className="tabular-nums text-muted-foreground">{item.importance.toFixed(3)}</span></div>
                      <div className="mt-2 h-1.5 bg-muted"><div className="h-full bg-prediction" style={{ width: `${Math.min(100, Math.abs(item.importance) / maxImportance * 100)}%` }} /></div>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            <section>
              <h3 className="mb-3 text-sm font-semibold">Contrato y variables</h3>
              <div className="flex flex-wrap gap-2">
                {model.features?.map((feature) => <Badge key={feature} variant="outline">{feature}</Badge>)}
              </div>
              {model.split_method ? <p className="mt-3 text-xs leading-5 text-muted-foreground"><strong>Separación:</strong> {model.split_method}</p> : null}
            </section>
          </div>
        </details>

        {model.limitations?.length ? (
          <Alert className="border-warning/35 bg-warning/5">
            <AlertTriangle className="text-warning" />
            <AlertTitle>Limitaciones que deben acompañar estas métricas</AlertTitle>
            <AlertDescription>
              <ul className="mt-2 list-disc space-y-1 pl-4">
                {model.limitations.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}

export default function ModelsPage() {
  const [models, setModels] = useState<ModelSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void api.getModels()
      .then((value) => { if (active) setModels(normalizeModels(value)); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "No fue posible cargar los modelos."); });
    return () => { active = false; };
  }, []);

  const hasModels = useMemo(() => Boolean(models?.length), [models]);

  return (
    <div className="app-page app-page-wide">
      <PageHeader
        eyebrow="Evidencia ML"
        title="Modelos y evidencia"
        description="Rendimiento y límites de los modelos oficiales."
      />

      <div className="flex items-start gap-3 border-l-2 border-agent px-3 text-sm text-muted-foreground">
        <Activity className="mt-0.5 size-4 shrink-0 text-agent" />
        <p>La validación física todavía requiere teléfono, OBS y red degradada.</p>
      </div>

      {error ? <Alert variant="destructive"><AlertTitle>Error</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}
      {models === null && !error ? <div className="py-8 text-center text-muted-foreground">Cargando evidencia oficial…</div> : null}
      {!hasModels && models !== null ? (
        <Card><CardContent className="flex flex-col items-center justify-center py-10 text-center"><Cpu className="mb-4 size-10 text-muted-foreground" /><div className="text-lg font-semibold">No hay metadata disponible</div><p className="text-sm text-muted-foreground">La API no devolvió modelos oficiales.</p></CardContent></Card>
      ) : null}

      <div className="grid min-w-0 gap-6">
        {models?.map((model, index) => <ModelEvidence key={`${model.role ?? "model"}-${index}`} model={model} />)}
      </div>
    </div>
  );
}
