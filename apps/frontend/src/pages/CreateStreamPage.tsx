import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import VideoConnectionMethod from "../components/VideoConnectionMethod";
import CopyLinkButton from "../components/CopyLinkButton";
import PageHeader from "../components/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { CheckCircle2, CircleDashed, Smartphone, Radio, Settings2, PlayCircle } from "lucide-react";
import type { StreamSession, VdoNinjaSession } from "../types";
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

type WizardStep = 1 | 2 | 3 | 4;

export default function CreateStreamPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<WizardStep>(1);
  const [name, setName] = useState("");
  const [platform, setPlatform] = useState("");
  const [resolution, setResolution] = useState("1080p");
  const [duration, setDuration] = useState("2");
  const [connectionType, setConnectionType] = useState("cable");
  
  const [session, setSession] = useState<StreamSession | null>(null);
  const [vdo, setVdo] = useState<VdoNinjaSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [appStatus, setAppStatus] = useState<"pending" | "connected">("pending");

  useEffect(() => {
    let active = true;
    void api.getSettings().then((settings) => {
      if (!active) return;
      setPlatform(settings.stream.platform);
      setResolution(settings.stream.preferred_resolution);
    }).catch(() => {
      // La creación sigue disponible con los valores por defecto del servidor.
    });
    return () => { active = false; };
  }, []);

  const safePhoneUrl = useMemo(() => {
    if (!vdo?.phone_url) return null;
    try {
      const url = new URL(vdo.phone_url);
      const allowed = new Set((import.meta.env.VITE_VDO_NINJA_ORIGINS || "https://vdo.ninja").split(",").map((item) => item.trim()));
      return allowed.has(url.origin) ? url.toString() : null;
    } catch { return null; }
  }, [vdo]);

  async function handleStep1Submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Por favor, ingresa un nombre para la transmisión.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await api.createSession(name, {
        platform: platform || undefined,
        resolution,
        planned_duration_hours: duration,
        connection_type: connectionType,
      });
      const created = response.session ?? {
        id: response.id ?? "",
        name: response.name,
        status: response.status,
        created_at: response.created_at,
        vdo_ninja: response.vdo_ninja,
        stream: response.stream,
      };
      if (!created.id) throw new Error("Ocurrió un error al iniciar la sesión.");
      setSession(created);
      setVdo(response.vdo_ninja ?? created.vdo_ninja ?? null);
      setStep(2);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible iniciar la configuración.");
    } finally { setBusy(false); }
  }

  function confirmAppConfiguration() {
    setAppStatus("connected");
  }

  return (
    <div className="app-page max-w-5xl">
      <PageHeader eyebrow={`Paso ${step} de 4`} title="Nueva transmisión" description="Configura la cámara, OBS y el monitoreo con una guía clara de cuatro pasos." />
      
      {/* Stepper Header */}
      <ol className="grid grid-cols-4 gap-1 rounded-2xl border border-border/80 bg-card p-2 shadow-sm sm:gap-3 sm:p-4">
        {[
          { num: 1, label: "Información", icon: Settings2 },
          { num: 2, label: "Teléfono", icon: Smartphone },
          { num: 3, label: "Aplicación", icon: Radio },
          { num: 4, label: "Comprobación", icon: CheckCircle2 }
        ].map((s, i) => (
          <li key={s.num} aria-current={step === s.num ? "step" : undefined} className={`flex min-w-0 flex-col items-center gap-2 rounded-xl px-1 py-2 text-center sm:px-3 ${step === s.num ? 'bg-primary/5 text-primary' : step > s.num ? 'text-primary/70' : 'text-muted-foreground'}`}>
            <div className={`flex size-9 items-center justify-center rounded-full border-2 transition-colors sm:size-10 ${step === s.num ? 'border-primary bg-primary/10' : step > s.num ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-muted/40'}`}>
              <s.icon className="size-4 sm:size-5" />
            </div>
            <span className="w-full truncate text-[10px] font-semibold sm:text-xs">{s.label}</span>
          </li>
        ))}
      </ol>

      <div className={step === 1 ? "block" : "hidden"}>
        <Card>
          <form onSubmit={handleStep1Submit}>
            <CardHeader>
              <CardTitle>Paso 1: Información básica</CardTitle>
              <CardDescription>Indícanos los detalles de tu evento para preparar el entorno.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="name">Nombre de la transmisión</Label>
                <Input id="name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Ej. Evento principal" maxLength={120} />
              </div>
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Plataforma de destino</Label>
                  <Select value={platform} onValueChange={setPlatform}>
                    <SelectTrigger className="w-full"><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="youtube">YouTube Live</SelectItem>
                      <SelectItem value="twitch">Twitch</SelectItem>
                      <SelectItem value="facebook">Facebook Live</SelectItem>
                      <SelectItem value="custom">Servidor personalizado</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Resolución deseada</Label>
                  <Select value={resolution} onValueChange={setResolution}>
                    <SelectTrigger className="w-full"><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1080p">1080p (Alta definición)</SelectItem>
                      <SelectItem value="720p">720p (Estándar)</SelectItem>
                      <SelectItem value="480p">480p (Básica)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Duración aproximada (horas)</Label>
                  <Select value={duration} onValueChange={setDuration}>
                    <SelectTrigger className="w-full"><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1 hora</SelectItem>
                      <SelectItem value="2">2 horas</SelectItem>
                      <SelectItem value="4">4 horas</SelectItem>
                      <SelectItem value="8">Más de 4 horas</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Tipo de conexión</Label>
                  <Select value={connectionType} onValueChange={setConnectionType}>
                    <SelectTrigger className="w-full"><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cable">Cable de red (Recomendado)</SelectItem>
                      <SelectItem value="wifi">Wi-Fi</SelectItem>
                      <SelectItem value="mobile">Datos móviles</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {error ? <Alert variant="destructive"><AlertTitle>Atención</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}
            </CardContent>
            <CardFooter className="flex justify-end border-t">
              <Button type="submit" className="w-full sm:w-auto" disabled={busy || !name}>{busy ? "Preparando..." : "Siguiente paso"}</Button>
            </CardFooter>
          </form>
        </Card>
      </div>

      <div className={step === 2 ? "block" : "hidden"}>
        <Card>
          <CardHeader>
            <CardTitle>Paso 2: Conectar teléfono</CardTitle>
            <CardDescription>Tu teléfono funcionará como cámara inalambrica de alta calidad.</CardDescription>
          </CardHeader>
          <CardContent className="min-w-0">
            <VideoConnectionMethod 
              safePhoneUrl={safePhoneUrl} 
              embedUrl={vdo?.embed_url || null}
              onContinue={() => setStep(3)}
              onLinkUpdated={async (newUrl) => {
                if (!session) throw new Error("Primero crea la transmisión antes de guardar el enlace.");
                const updated = await api.updateVideoLink(session.id, newUrl);
                setVdo((current) => current ? { ...current, embed_url: updated.embed_url, source: "external" } : current);
              }}
            />
          </CardContent>
          <CardFooter className="flex justify-between border-t">
            <Button variant="ghost" onClick={() => setStep(1)}>Volver</Button>
          </CardFooter>
        </Card>
      </div>

      <div className={step === 3 ? "block" : "hidden"}>
        <Card>
          <CardHeader>
            <CardTitle>Paso 3: Agregar el video a tu aplicación de transmisión</CardTitle>
            <CardDescription>Vincula tu programa de transmisión con StreamML.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="rounded-2xl border border-border/70 bg-muted/30 p-5 sm:p-6">
                <h4 className="font-semibold mb-4">Instrucciones:</h4>
                <ol className="list-decimal list-inside space-y-3 text-sm">
                  <li>Copia el enlace a continuación.</li>
                  <li>Abre OBS (o tu software preferido).</li>
                  <li>Agrega una nueva fuente de navegador (Browser Source).</li>
                  <li>Pega el enlace en la URL.</li>
                  <li>Comprueba que el video aparezca.</li>
                  <li>Regresa a StreamML y confirma que agregaste la fuente.</li>
                </ol>
                <div className="mt-6">
                  <CopyLinkButton link={vdo?.embed_url || null} className="w-full" />
                </div>
              </div>
              
              <div className="flex min-h-72 flex-col items-center justify-center gap-4 rounded-2xl border bg-muted/10 px-5 py-8">
                {appStatus === "pending" && (
                  <>
                    <Radio className="size-12 text-muted-foreground opacity-50" />
                    <div className="text-center">
                      <p className="font-medium">Confirmación pendiente</p>
                      <p className="text-sm text-muted-foreground">StreamML no controla ni inspecciona visualmente la fuente de OBS.</p>
                    </div>
                    <div className="flex flex-col gap-2 w-full px-6">
                      <Button onClick={confirmAppConfiguration}>Confirmar que lo agregué</Button>
                    </div>
                  </>
                )}
                {appStatus === "connected" && (
                  <>
                    <div className="size-16 bg-green-500/10 rounded-full flex items-center justify-center text-green-500">
                      <CheckCircle2 className="size-8" />
                    </div>
                    <div className="text-center">
                      <p className="font-medium text-green-600">Configuración confirmada</p>
                      <p className="text-sm text-muted-foreground">Comprueba visualmente la fuente de navegador dentro de OBS.</p>
                    </div>
                  </>
                )}
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex justify-between border-t">
            <Button variant="ghost" onClick={() => setStep(2)}>Volver</Button>
            <Button onClick={() => setStep(4)} disabled={appStatus !== "connected"}>
              Continuar
            </Button>
          </CardFooter>
        </Card>
      </div>

      <div className={step === 4 ? "block" : "hidden"}>
        <Card>
          <CardHeader>
            <CardTitle>Paso 4: Comprobación previa</CardTitle>
            <CardDescription>Revisa que todo esté listo antes de comenzar a transmitir.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              {[
                { label: "Sesión creada en StreamML", ready: Boolean(session), detail: "Registrada" },
                { label: "Enlace de cámara configurado", ready: Boolean(vdo?.embed_url), detail: vdo?.embed_url ? "Configurado" : "Pendiente" },
                { label: "Fuente agregada en OBS", ready: appStatus === "connected", detail: appStatus === "connected" ? "Confirmado por ti" : "Pendiente" },
                { label: "Telemetría de OBS", ready: false, detail: "Se validará en monitoreo" },
                { label: "Variables para predicción", ready: false, detail: "Dependen de datos reales" },
              ].map((item) => (
                <div key={item.label} className={`flex items-center justify-between gap-4 rounded-xl border p-4 ${item.ready ? "border-green-500/20 bg-green-500/5" : "border-border bg-muted/20"}`}>
                  <div className="flex min-w-0 items-center gap-3">
                    {item.ready ? <CheckCircle2 className="size-5 shrink-0 text-green-600" /> : <CircleDashed className="size-5 shrink-0 text-muted-foreground" />}
                    <span className="font-medium">{item.label}</span>
                  </div>
                  <span className={`shrink-0 text-right text-xs sm:text-sm ${item.ready ? "text-green-700" : "text-muted-foreground"}`}>{item.detail}</span>
                </div>
              ))}
            </div>
            
            <div className="rounded-xl bg-primary/10 p-4 text-center">
              <p className="text-sm font-medium">La configuración inicial quedó registrada.</p>
              <p className="mt-1 text-xs text-muted-foreground">El agente podrá ajustar el perfil de OBS y cambiar entre las escenas StreamML Live y StreamML Backup mediante comandos autenticados.</p>
            </div>
          </CardContent>
          <CardFooter className="flex flex-col-reverse gap-3 border-t sm:flex-row sm:justify-between">
            <Button variant="ghost" onClick={() => setStep(3)}>Volver</Button>
            <Button size="lg" className="w-full gap-2 sm:w-auto" onClick={() => navigate(`/sessions/${encodeURIComponent(session!.id)}/live`)}>
              <PlayCircle className="size-5" />
              Abrir monitoreo
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
