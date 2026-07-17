import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../App";
import { Activity } from "lucide-react";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden bg-muted/20 p-5 sm:p-8">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,color-mix(in_oklab,var(--primary)_10%,transparent),transparent_36rem)]" />
      <div className="relative flex w-full max-w-md flex-col gap-6">
        <div className="flex items-center gap-3 self-center">
          <div className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lg shadow-primary/20">
            <Activity className="size-4" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="font-bold tracking-tight">StreamML</span>
            <span className="text-xs text-muted-foreground">Adaptive Engine</span>
          </div>
        </div>
        
        <Card className="border-border/80 bg-card/95 shadow-xl shadow-slate-950/5 backdrop-blur">
          <CardHeader>
            <CardTitle className="text-2xl">Iniciar sesión</CardTitle>
            <CardDescription>
              Usa las credenciales de tu cuenta StreamML para acceder al monitor en tiempo real.
            </CardDescription>
          </CardHeader>
          <form onSubmit={submit}>
            <CardContent className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="email">Correo electrónico</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="m@example.com"
                  autoComplete="username"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </div>
              <div className="grid gap-2">
                <div className="flex items-center">
                  <Label htmlFor="password">Contraseña</Label>
                </div>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </div>
              
              {error ? (
                <div className="text-sm font-medium text-destructive">{error}</div>
              ) : null}
              
              <Button type="submit" size="lg" className="mt-1 w-full" disabled={busy}>
                {busy ? "Verificando…" : "Iniciar sesión"}
              </Button>
            </CardContent>
            <CardFooter>
              <div className="text-balance text-center text-xs text-muted-foreground w-full">
                La sesión se mantiene mediante una cookie segura HttpOnly. StreamML no guarda tu contraseña en el navegador.
              </div>
            </CardFooter>
          </form>
        </Card>
      </div>
    </main>
  );
}
