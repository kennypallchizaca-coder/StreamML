import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Activity, BrainCircuit, Eye, EyeOff, LoaderCircle, LockKeyhole, Radio, ShieldCheck } from "@/components/icons";
import { useAuth } from "../App";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

const capabilities = [
  { icon: Radio, title: "Control adaptativo", text: "Ajusta el perfil según las condiciones reales de red." },
  { icon: BrainCircuit, title: "Predicción anticipada", text: "Detecta reducciones de calidad antes de una interrupción." },
  { icon: ShieldCheck, title: "Operación protegida", text: "Autenticación segura y respaldo automático de señal." },
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      const destination = typeof location.state === "object" && location.state && "from" in location.state
        ? String(location.state.from)
        : "/dashboard";
      navigate(destination, { replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible iniciar sesión.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-svh bg-background lg:grid-cols-[minmax(24rem,0.9fr)_minmax(28rem,1.1fr)]">
      <section className="technical-grid relative hidden overflow-hidden border-r bg-sidebar p-8 text-sidebar-foreground lg:flex lg:flex-col xl:p-10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,color-mix(in_oklab,var(--sidebar-primary)_18%,transparent),transparent_35rem)]" />
        <div className="relative flex items-center gap-3">
          <div className="relative flex size-10 items-center justify-center rounded-xl bg-sidebar-primary text-sidebar-primary-foreground shadow-[var(--shadow-lg)]">
            <Activity className="size-5" />
            <span className="absolute -right-0.5 -top-0.5 size-2.5 rounded-full border-2 border-sidebar bg-success" />
          </div>
          <div>
            <p className="font-semibold tracking-tight">StreamML</p>
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-sidebar-foreground/45">Adaptive Control</p>
          </div>
        </div>

        <div className="relative my-auto max-w-xl py-8">
          <BadgeLabel />
          <h1 className="mt-4 text-4xl font-semibold leading-[1.12] tracking-[-0.04em] xl:text-5xl">
            Tu transmisión,<br />protegida antes del fallo.
          </h1>
          <p className="mt-4 max-w-lg text-sm leading-6 text-sidebar-foreground/55">
            Monitoriza la red, recibe recomendaciones de Machine Learning y permite que el agente autónomo actúe antes de que la calidad se degrade.
          </p>
          <div className="mt-6 grid gap-2">
            {capabilities.map((item) => (
              <div key={item.title} className="flex items-start gap-3 rounded-xl border border-sidebar-border bg-sidebar/70 p-3 backdrop-blur-sm">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-accent text-sidebar-primary"><item.icon className="size-4" /></span>
                <div><p className="text-sm font-medium">{item.title}</p><p className="mt-0.5 text-xs leading-4 text-sidebar-foreground/45">{item.text}</p></div>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-xs text-sidebar-foreground/35">StreamML · Centro de operación inteligente</p>
      </section>

      <section className="relative flex items-center justify-center overflow-hidden p-5 sm:p-8 lg:p-12">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_70%_0%,color-mix(in_oklab,var(--primary)_8%,transparent),transparent_30rem)]" />
        <div className="relative w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Activity className="size-4" /></div>
            <div><p className="text-sm font-semibold">StreamML</p><p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Adaptive Control</p></div>
          </div>

          <Card className="border-border/80 bg-card/90 shadow-[var(--shadow-lg)] backdrop-blur">
            <CardHeader className="pb-1">
              <span className="mb-3 flex size-10 items-center justify-center rounded-xl border bg-muted/30 text-muted-foreground"><LockKeyhole className="size-4.5" /></span>
              <CardTitle className="text-2xl tracking-[-0.025em]">Accede al centro de control</CardTitle>
              <CardDescription className="leading-6">Ingresa con la cuenta de administrador configurada durante la instalación.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={submit} className="grid gap-5">
                <div className="grid gap-2">
                  <Label htmlFor="email">Correo electrónico</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="admin@streamml.local"
                    autoComplete="username"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                    disabled={busy}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="password">Contraseña</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      required
                      disabled={busy}
                      className="pr-11"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((visible) => !visible)}
                      className="absolute right-1.5 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                    >
                      {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>

                {error ? (
                  <Alert variant="destructive" role="alert"><AlertDescription>{error}</AlertDescription></Alert>
                ) : null}

                <Button type="submit" size="lg" className="mt-1 w-full" disabled={busy}>
                  {busy ? <><LoaderCircle className="animate-spin" />Verificando acceso…</> : "Iniciar sesión"}
                </Button>
                <p className="text-center text-[11px] leading-5 text-muted-foreground">
                  La sesión usa una cookie HttpOnly. La contraseña no se almacena en el navegador.
                </p>
              </form>
            </CardContent>
          </Card>
        </div>
      </section>
    </main>
  );
}

function BadgeLabel() {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-sidebar-border bg-sidebar-accent/60 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-sidebar-foreground/70">
      <span className="size-1.5 rounded-full bg-success" />Streaming adaptativo con ML
    </span>
  );
}
