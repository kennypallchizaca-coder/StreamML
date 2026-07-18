import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, normalizeSessions } from "../api";
import { useAuth } from "../App";
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Switch } from "../components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import type { PreferencesSettings, SettingsResponse, StreamSession, StreamSettings } from "../types";
import { CheckCircle2, Download, ExternalLink, Link2, LoaderCircle, LogOut, RefreshCw, Settings, ShieldAlert, Trash2, User, Video } from "@/components/icons";
import PageHeader from "../components/PageHeader";

type Notice = { tone: "success" | "error" | "info"; text: string } | null;

const initialPreferences: PreferencesSettings = {
  language: "es", timezone: "auto", dark_mode: true, alert_detail: "normal",
};
const initialStream: StreamSettings = {
  preferred_resolution: "1080p", preferred_profile: "high", platform: "youtube",
  live_scene: "StreamML Live", backup_scene: "StreamML Backup",
  network_probe_interval_seconds: 5, network_probe_bytes: 262144,
};

function Message({ notice }: { notice: Notice }) {
  if (!notice) return null;
  return (
    <Alert variant={notice.tone === "error" ? "destructive" : "default"} className={notice.tone === "success" ? "border-success/30 bg-success-muted" : undefined}>
      {notice.tone === "success" ? <CheckCircle2 className="text-success" /> : null}
      <AlertTitle>{notice.tone === "success" ? "Guardado" : notice.tone === "error" ? "No fue posible completar la acción" : "Información"}</AlertTitle>
      <AlertDescription>{notice.text}</AlertDescription>
    </Alert>
  );
}

function errorText(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}

function pairingSessionLabel(session: StreamSession) {
  const created = session.created_at
    ? new Date(session.created_at).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" })
    : "fecha no disponible";
  const state = session.status === "ready" ? "lista" : session.status === "created" ? "sin vincular" : session.status || "sin estado";
  return `${session.name || "Transmisión sin nombre"} · ${created} · ${state} · …${session.id.slice(-8)}`;
}

export default function SettingsPage() {
  const { user, logout, updateUser } = useAuth();
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [sessions, setSessions] = useState<StreamSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<Notice>(null);
  const [accountBusy, setAccountBusy] = useState(false);
  const [preferencesBusy, setPreferencesBusy] = useState(false);
  const [streamBusy, setStreamBusy] = useState(false);
  const [pairingBusy, setPairingBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [displayName, setDisplayName] = useState(user?.display_name || user?.email || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [preferences, setPreferences] = useState<PreferencesSettings>(initialPreferences);
  const [stream, setStream] = useState<StreamSettings>(initialStream);
  const [pairingSessionId, setPairingSessionId] = useState("");
  const [pairingCode, setPairingCode] = useState<{ code: string; expires_at?: string | null } | null>(null);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [accountDialogOpen, setAccountDialogOpen] = useState(false);
  const [destructiveBusy, setDestructiveBusy] = useState(false);
  const [accountDeletionPassword, setAccountDeletionPassword] = useState("");
  const [accountConfirmation, setAccountConfirmation] = useState("");

  const connectors = useMemo(() => settings?.connectors ?? [], [settings?.connectors]);
  const connectorStatus = useMemo(() => connectors.some((connector) => connector.connected), [connectors]);
  const selectedSessionConnector = useMemo(
    () => connectors.find((connector) => connector.session_id === pairingSessionId),
    [connectors, pairingSessionId],
  );

  async function loadConfiguration(showNotice = false) {
    try {
      const [nextSettings, list] = await Promise.all([api.getSettings(), api.listSessions()]);
      setSettings(nextSettings);
      setSessions(normalizeSessions(list));
      setDisplayName(nextSettings.user.display_name || nextSettings.user.email || "");
      setPreferences(nextSettings.preferences);
      setStream(nextSettings.stream);
      setPairingSessionId((selected) => selected || normalizeSessions(list)[0]?.id || "");
      document.documentElement.classList.toggle("dark", nextSettings.preferences.dark_mode);
      if (showNotice) setNotice({ tone: "success", text: "Se actualizó el estado de la configuración y del conector." });
    } catch (reason) {
      setNotice({ tone: "error", text: errorText(reason, "No pudimos cargar la configuración.") });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadConfiguration(); }, []);

  async function saveAccount(event: FormEvent) {
    event.preventDefault();
    if (!displayName.trim()) {
      setNotice({ tone: "error", text: "Escribe un nombre para tu perfil." });
      return;
    }
    if (newPassword || confirmPassword || currentPassword) {
      if (!currentPassword) {
        setNotice({ tone: "error", text: "Ingresa tu contraseña actual para cambiarla." });
        return;
      }
      if (newPassword.length < 12) {
        setNotice({ tone: "error", text: "La nueva contraseña debe tener al menos 12 caracteres." });
        return;
      }
      if (newPassword !== confirmPassword) {
        setNotice({ tone: "error", text: "La confirmación de la contraseña no coincide." });
        return;
      }
    }
    setAccountBusy(true);
    setNotice(null);
    try {
      const response = await api.updateAccount({
        display_name: displayName.trim(),
        ...(newPassword ? { current_password: currentPassword, new_password: newPassword } : {}),
      });
      if (response.user) updateUser(response.user);
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      setNotice({ tone: "success", text: "Los datos de tu cuenta se guardaron correctamente." });
    } catch (reason) {
      setNotice({ tone: "error", text: errorText(reason, "No pudimos guardar la cuenta.") });
    } finally { setAccountBusy(false); }
  }

  async function savePreferences() {
    setPreferencesBusy(true); setNotice(null);
    try {
      const response = await api.updatePreferences(preferences);
      setPreferences(response.preferences);
      document.documentElement.classList.toggle("dark", response.preferences.dark_mode);
      setNotice({ tone: "success", text: "Las preferencias se guardaron y se conservarán al reiniciar." });
    } catch (reason) {
      setNotice({ tone: "error", text: errorText(reason, "No pudimos guardar las preferencias.") });
    } finally { setPreferencesBusy(false); }
  }

  async function saveStream() {
    if (!stream.live_scene.trim() || !stream.backup_scene.trim()) {
      setNotice({ tone: "error", text: "Indica los nombres de las escenas en OBS." });
      return;
    }
    setStreamBusy(true); setNotice(null);
    try {
      const response = await api.updateStreamSettings({
        ...stream, live_scene: stream.live_scene.trim(), backup_scene: stream.backup_scene.trim(),
        network_probe_interval_seconds: Number(stream.network_probe_interval_seconds),
        network_probe_bytes: Number(stream.network_probe_bytes),
      });
      setStream(response.stream);
      setNotice({ tone: "success", text: "Los ajustes se guardaron. El conector los aplicará en su próxima sincronización (máximo 30 segundos)." });
    } catch (reason) {
      setNotice({ tone: "error", text: errorText(reason, "No pudimos guardar los ajustes de transmisión.") });
    } finally { setStreamBusy(false); }
  }

  async function generatePairingCode() {
    if (!pairingSessionId) {
      setNotice({ tone: "error", text: "Crea o selecciona una transmisión antes de vincular OBS." });
      return;
    }
    setPairingBusy(true); setNotice(null); setPairingCode(null);
    try {
      const code = await api.createPairingCode(pairingSessionId);
      setPairingCode(code);
      setNotice({ tone: "success", text: "Código temporal creado. Escríbelo en StreamML Connector antes de que caduque." });
    } catch (reason) {
      setNotice({ tone: "error", text: errorText(reason, "No pudimos generar el código de vinculación.") });
    } finally { setPairingBusy(false); }
  }

  async function downloadExport() {
    setExporting(true); setNotice(null);
    try {
      const data = await api.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = `streamml-datos-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
      setNotice({ tone: "success", text: "Se descargó una copia de tus ajustes e historial." });
    } catch (reason) {
      setNotice({ tone: "error", text: errorText(reason, "No pudimos preparar la descarga.") });
    } finally { setExporting(false); }
  }

  async function deleteHistory() {
    setDestructiveBusy(true);
    try {
      const response = await api.deleteHistory();
      setSessions([]); setPairingSessionId(""); setPairingCode(null); setHistoryDialogOpen(false);
      setNotice({ tone: "success", text: `Se eliminaron ${response.deleted_sessions} transmisiones y sus datos asociados.` });
      await loadConfiguration();
    } catch (reason) {
      setNotice({ tone: "error", text: errorText(reason, "No pudimos borrar el historial.") });
    } finally { setDestructiveBusy(false); }
  }

  async function deleteAccount() {
    if (accountConfirmation !== `DELETE ${user?.email || ""}`) {
      setNotice({ tone: "error", text: "La frase de confirmación no coincide con tu correo." });
      return;
    }
    if (!accountDeletionPassword) {
      setNotice({ tone: "error", text: "Ingresa tu contraseña actual para eliminar la cuenta." });
      return;
    }
    setDestructiveBusy(true);
    try {
      await api.deleteAccount(accountConfirmation, accountDeletionPassword);
      setAccountDialogOpen(false);
      await logout();
    } catch (reason) {
      setNotice({ tone: "error", text: errorText(reason, "No pudimos eliminar la cuenta.") });
    } finally { setDestructiveBusy(false); }
  }

  if (loading) return <main className="route-loading" aria-live="polite">Cargando configuración…</main>;

  return (
    <div className="app-page max-w-5xl">
      <PageHeader eyebrow="Cuenta" title="Configuración" description="Administra tu cuenta, preferencias y transmisión desde un único lugar." />
      <Message notice={notice} />

      <Tabs defaultValue="account" className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-2 gap-1 rounded-xl p-1 sm:grid-cols-3 lg:grid-cols-5">
          <TabsTrigger value="account" className="gap-2"><User className="size-4" /> Cuenta</TabsTrigger>
          <TabsTrigger value="preferences" className="gap-2"><Settings className="size-4" /> Preferencias</TabsTrigger>
          <TabsTrigger value="stream" className="gap-2"><Video className="size-4" /> Transmisión</TabsTrigger>
          <TabsTrigger value="connections" className="gap-2"><Link2 className="size-4" /> Conexiones</TabsTrigger>
          <TabsTrigger value="privacy" className="gap-2"><ShieldAlert className="size-4" /> Datos</TabsTrigger>
        </TabsList>

        <TabsContent value="account" className="mt-6 space-y-6">
          <Card>
            <form onSubmit={saveAccount}>
              <CardHeader><CardTitle>Detalles de la cuenta</CardTitle><CardDescription>El correo identifica la cuenta; el nombre se muestra solo dentro de StreamML.</CardDescription></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2"><Label htmlFor="display-name">Nombre</Label><Input id="display-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} maxLength={100} required /></div>
                <div className="space-y-2"><Label htmlFor="account-email">Correo electrónico</Label><Input id="account-email" value={user?.email || ""} disabled /></div>
                <div className="grid gap-4 border-t pt-5 sm:grid-cols-2">
                  <div className="space-y-2"><Label htmlFor="current-password">Contraseña actual</Label><Input id="current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" /></div>
                  <div className="space-y-2"><Label htmlFor="new-password">Nueva contraseña</Label><Input id="new-password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} minLength={12} autoComplete="new-password" /></div>
                  <div className="space-y-2 sm:col-span-2"><Label htmlFor="confirm-password">Confirmar nueva contraseña</Label><Input id="confirm-password" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} minLength={12} autoComplete="new-password" /></div>
                </div>
                <p className="text-xs text-muted-foreground">Deja los campos de contraseña vacíos si no deseas cambiarla. Si la cambias, se requiere la contraseña actual.</p>
              </CardContent>
              <CardFooter className="flex flex-col-reverse items-stretch justify-between gap-3 border-t sm:flex-row sm:items-center">
                <Button type="button" variant="outline" onClick={() => void logout()} className="text-destructive hover:bg-destructive/10 hover:text-destructive"><LogOut className="mr-2 size-4" /> Cerrar sesión</Button>
                <Button type="submit" disabled={accountBusy}>{accountBusy ? <LoaderCircle className="animate-spin" /> : null}Guardar cuenta</Button>
              </CardFooter>
            </form>
          </Card>
        </TabsContent>

        <TabsContent value="preferences" className="mt-6 space-y-6">
          <Card>
            <CardHeader><CardTitle>Preferencias generales</CardTitle><CardDescription>Estas preferencias se guardan en tu cuenta y se recuperan al volver a entrar.</CardDescription></CardHeader>
            <CardContent className="space-y-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><Label>Idioma</Label><p className="text-sm text-muted-foreground">Idioma disponible en la interfaz.</p></div><Select value={preferences.language} onValueChange={(language: PreferencesSettings["language"]) => setPreferences({ ...preferences, language })}><SelectTrigger className="w-full sm:w-52"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="es">Español</SelectItem></SelectContent></Select></div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><Label>Zona horaria</Label><p className="text-sm text-muted-foreground">Usada al mostrar fechas e historial.</p></div><Select value={preferences.timezone} onValueChange={(timezone: PreferencesSettings["timezone"]) => setPreferences({ ...preferences, timezone })}><SelectTrigger className="w-full sm:w-52"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="auto">Automática</SelectItem><SelectItem value="America/Guayaquil">Ecuador (Guayaquil)</SelectItem><SelectItem value="UTC">UTC</SelectItem></SelectContent></Select></div>
              <div className="flex items-center justify-between gap-4"><div><Label htmlFor="dark-mode">Tema oscuro</Label><p className="text-sm text-muted-foreground">Se aplica al panel y se transmite al asistente local cuando lo abres.</p></div><Switch id="dark-mode" checked={preferences.dark_mode} onCheckedChange={(dark_mode) => setPreferences({ ...preferences, dark_mode })} /></div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><Label>Detalle de alertas</Label><p className="text-sm text-muted-foreground">Cantidad de contexto mostrado en los avisos.</p></div><Select value={preferences.alert_detail} onValueChange={(alert_detail: PreferencesSettings["alert_detail"]) => setPreferences({ ...preferences, alert_detail })}><SelectTrigger className="w-full sm:w-52"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="low">Reducido</SelectItem><SelectItem value="normal">Normal</SelectItem><SelectItem value="high">Detallado</SelectItem></SelectContent></Select></div>
            </CardContent>
            <CardFooter className="border-t"><Button onClick={() => void savePreferences()} disabled={preferencesBusy}>{preferencesBusy ? <LoaderCircle className="animate-spin" /> : null}Guardar preferencias</Button></CardFooter>
          </Card>
        </TabsContent>

        <TabsContent value="stream" className="mt-6 space-y-6">
          <Card>
            <CardHeader><CardTitle>Ajustes de transmisión</CardTitle><CardDescription>Se usan al crear nuevas transmisiones. Las escenas y las sondas también llegan al conector OBS vinculado.</CardDescription></CardHeader>
            <CardContent className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-2"><Label>Resolución preferida</Label><Select value={stream.preferred_resolution} onValueChange={(preferred_resolution: StreamSettings["preferred_resolution"]) => setStream({ ...stream, preferred_resolution })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="1080p">1080p</SelectItem><SelectItem value="720p">720p</SelectItem><SelectItem value="480p">480p</SelectItem></SelectContent></Select></div>
              <div className="space-y-2"><Label>Perfil inicial</Label><Select value={stream.preferred_profile} onValueChange={(preferred_profile: StreamSettings["preferred_profile"]) => setStream({ ...stream, preferred_profile })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="high">Alto</SelectItem><SelectItem value="medium">Medio</SelectItem><SelectItem value="low">Básico</SelectItem></SelectContent></Select></div>
              <div className="space-y-2"><Label>Plataforma principal</Label><Select value={stream.platform} onValueChange={(platform: StreamSettings["platform"]) => setStream({ ...stream, platform })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="youtube">YouTube Live</SelectItem><SelectItem value="twitch">Twitch</SelectItem><SelectItem value="facebook">Facebook Live</SelectItem><SelectItem value="kick">Kick</SelectItem><SelectItem value="custom">Servidor personalizado</SelectItem></SelectContent></Select></div>
              <div className="space-y-2"><Label htmlFor="probe-interval">Frecuencia de medición de red (segundos)</Label><Input id="probe-interval" type="number" min="1" max="60" value={stream.network_probe_interval_seconds} onChange={(event) => setStream({ ...stream, network_probe_interval_seconds: Number(event.target.value) })} /></div>
              <div className="space-y-2"><Label htmlFor="live-scene">Escena de señal en vivo (OBS)</Label><Input id="live-scene" value={stream.live_scene} onChange={(event) => setStream({ ...stream, live_scene: event.target.value })} maxLength={120} /></div>
              <div className="space-y-2"><Label htmlFor="backup-scene">Escena de respaldo (OBS)</Label><Input id="backup-scene" value={stream.backup_scene} onChange={(event) => setStream({ ...stream, backup_scene: event.target.value })} maxLength={120} /></div>
              <div className="space-y-2 sm:col-span-2"><Label htmlFor="probe-bytes">Tamaño de cada sonda de red (bytes)</Label><Input id="probe-bytes" type="number" min="1024" max="524288" step="1024" value={stream.network_probe_bytes} onChange={(event) => setStream({ ...stream, network_probe_bytes: Number(event.target.value) })} /><p className="text-xs text-muted-foreground">Entre 1 KiB y 512 KiB. Un valor menor consume menos datos móviles.</p></div>
            </CardContent>
            <CardFooter className="border-t"><Button onClick={() => void saveStream()} disabled={streamBusy}>{streamBusy ? <LoaderCircle className="animate-spin" /> : null}Guardar ajustes de transmisión</Button></CardFooter>
          </Card>
        </TabsContent>

        <TabsContent value="connections" className="mt-6 space-y-6">
          <Card className="border-primary/30 bg-primary/5">
            <CardHeader><CardTitle>Asistente local de configuración</CardTitle><CardDescription>Configura OBS, guarda su contraseña cifrada en Windows, valida la conexión y arranca el monitor sin editar archivos ni usar comandos.</CardDescription></CardHeader>
            <CardContent className="space-y-3"><p className="text-sm text-muted-foreground">Si es la primera vez, abre <strong>Abrir-Configuracion-StreamML.cmd</strong> dentro de la carpeta <strong>scripts</strong> del proyecto. Después usa este botón para continuar en el asistente local.</p><Button asChild><a href={`http://127.0.0.1:8765/?theme=${preferences.dark_mode ? "dark" : "light"}`} target="_blank" rel="noopener noreferrer">Abrir asistente local <ExternalLink /></a></Button></CardContent>
          </Card>
          <Card>
            <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between"><div><CardTitle>Vincular StreamML Connector</CardTitle><CardDescription>Genera un código temporal para la aplicación local que se conecta a OBS.</CardDescription></div><Button variant="outline" size="sm" onClick={() => void loadConfiguration(true)}><RefreshCw className="mr-2 size-4" />Comprobar estado</Button></CardHeader>
            <CardContent className="space-y-5">
              <div className="rounded-xl border bg-muted/20 p-4"><p className="font-medium">Estado del conector: <span className={connectorStatus ? "text-success" : "text-warning"}>{connectorStatus ? "conectado recientemente" : "sin conexión reciente"}</span></p><p className="mt-1 text-sm text-muted-foreground">{connectors.length ? connectors.map((connector) => `${connector.name}${connector.last_seen_at ? ` · última señal ${new Date(connector.last_seen_at).toLocaleString()}` : " · pendiente"}`).join("; ") : "Aún no hay un conector vinculado."}</p></div>
              <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto]"><div className="space-y-2"><Label>Transmisión para vincular</Label><Select value={pairingSessionId} onValueChange={(value) => { setPairingSessionId(value); setPairingCode(null); }}><SelectTrigger><SelectValue placeholder="Selecciona una transmisión" /></SelectTrigger><SelectContent>{sessions.map((session) => <SelectItem key={session.id} value={session.id}>{pairingSessionLabel(session)}</SelectItem>)}</SelectContent></Select><p className={`text-xs ${selectedSessionConnector?.connected ? "text-success" : "text-warning"}`}>{selectedSessionConnector?.connected ? `Esta transmisión recibe datos de ${selectedSessionConnector.name}.` : "Esta transmisión todavía no tiene un conector activo. Genera un código y vincúlala en el asistente local."}</p></div><div className="flex items-end"><Button onClick={() => void generatePairingCode()} disabled={pairingBusy || !pairingSessionId}>{pairingBusy ? <LoaderCircle className="animate-spin" /> : <Link2 />}Generar código</Button></div></div>
              {pairingCode ? <div className="rounded-xl border border-primary/30 bg-primary/5 p-4"><p className="text-sm font-medium">Código de un solo uso</p><p className="mt-2 break-all font-mono text-2xl font-bold tracking-[0.2em]">{pairingCode.code}</p><p className="mt-2 text-sm text-muted-foreground">Caduca: {pairingCode.expires_at ? new Date(pairingCode.expires_at).toLocaleTimeString() : "pronto"}. Introdúcelo en StreamML Connector con la opción de vincular.</p></div> : null}
            </CardContent>
          </Card>
          <Card><CardHeader><CardTitle>Credenciales y conexiones protegidas</CardTitle><CardDescription>La interfaz no guarda secretos que deben permanecer fuera del navegador.</CardDescription></CardHeader><CardContent><Alert><ShieldAlert /><AlertTitle>Configuración segura</AlertTitle><AlertDescription>{settings?.security?.message || "Las credenciales sensibles se administran fuera de la interfaz."}</AlertDescription></Alert><p className="mt-4 text-sm text-muted-foreground">Configura la contraseña de OBS directamente en el conector local. Las claves RTMP se mantienen en tu plataforma de destino o en el servidor, nunca en esta página.</p></CardContent></Card>
        </TabsContent>

        <TabsContent value="privacy" className="mt-6 space-y-6">
          <Card className="border-destructive/20"><CardHeader><CardTitle className="text-destructive">Privacidad y datos</CardTitle><CardDescription>Las acciones destructivas solicitan una confirmación explícita.</CardDescription></CardHeader><CardContent className="space-y-4">
            <div className="flex flex-col items-start justify-between gap-4 rounded-lg border p-4 sm:flex-row sm:items-center"><div><h4 className="font-semibold">Descargar mis datos</h4><p className="text-sm text-muted-foreground">Incluye configuración, sesiones, telemetría y predicciones disponibles.</p></div><Button variant="secondary" onClick={() => void downloadExport()} disabled={exporting}>{exporting ? <LoaderCircle className="animate-spin" /> : <Download />}Descargar JSON</Button></div>
            <div className="flex flex-col items-start justify-between gap-4 rounded-lg border border-destructive/20 bg-destructive/5 p-4 sm:flex-row sm:items-center"><div><h4 className="font-semibold text-destructive">Eliminar historial</h4><p className="text-sm text-destructive/80">Borra permanentemente las transmisiones y telemetrías, pero conserva tu cuenta y tus preferencias.</p></div><Button variant="destructive" onClick={() => setHistoryDialogOpen(true)}><Trash2 />Borrar historial</Button></div>
            <div className="flex flex-col items-start justify-between gap-4 rounded-lg border border-destructive/20 bg-destructive/5 p-4 sm:flex-row sm:items-center"><div><h4 className="font-semibold text-destructive">Eliminar cuenta</h4><p className="text-sm text-destructive/80">Borra la cuenta y todos los datos asociados. Esta acción no se puede revertir.</p></div><Button variant="destructive" onClick={() => setAccountDialogOpen(true)}><Trash2 />Eliminar cuenta</Button></div>
          </CardContent></Card>
        </TabsContent>
      </Tabs>

      <Dialog open={historyDialogOpen} onOpenChange={setHistoryDialogOpen}><DialogContent><DialogHeader><DialogTitle>¿Borrar todo el historial?</DialogTitle><DialogDescription>Se eliminarán las sesiones, telemetrías, predicciones y vínculos del conector asociados. La cuenta y los ajustes se conservarán.</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" onClick={() => setHistoryDialogOpen(false)} disabled={destructiveBusy}>Cancelar</Button><Button variant="destructive" onClick={() => void deleteHistory()} disabled={destructiveBusy}>{destructiveBusy ? <LoaderCircle className="animate-spin" /> : null}Sí, borrar historial</Button></DialogFooter></DialogContent></Dialog>
      <Dialog open={accountDialogOpen} onOpenChange={setAccountDialogOpen}><DialogContent><DialogHeader><DialogTitle>Eliminar cuenta permanentemente</DialogTitle><DialogDescription>Para confirmar, escribe <strong>{`DELETE ${user?.email || ""}`}</strong> y tu contraseña actual.</DialogDescription></DialogHeader><div className="space-y-4"><div className="space-y-2"><Label htmlFor="account-confirmation">Frase de confirmación</Label><Input id="account-confirmation" value={accountConfirmation} onChange={(event) => setAccountConfirmation(event.target.value)} autoComplete="off" /></div><div className="space-y-2"><Label htmlFor="account-delete-password">Contraseña actual</Label><Input id="account-delete-password" type="password" value={accountDeletionPassword} onChange={(event) => setAccountDeletionPassword(event.target.value)} autoComplete="current-password" /></div></div><DialogFooter><Button variant="outline" onClick={() => setAccountDialogOpen(false)} disabled={destructiveBusy}>Cancelar</Button><Button variant="destructive" onClick={() => void deleteAccount()} disabled={destructiveBusy}>{destructiveBusy ? <LoaderCircle className="animate-spin" /> : null}Eliminar definitivamente</Button></DialogFooter></DialogContent></Dialog>
    </div>
  );
}
