import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, LoaderCircle, LockKeyhole, Mail, UserPlus } from "@/components/icons";
import { useAuth } from "../App";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import NexaMascot from "../components/NexaMascot";
import { toast } from "sonner";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [registerName, setRegisterName] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerConfirm, setRegisterConfirm] = useState("");

  async function handleLogin(event: FormEvent) {
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

  function handleRegister(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    if (registerPassword !== registerConfirm) {
      setError("Las contraseñas no coinciden.");
      setBusy(false);
      return;
    }

    // Mock API call delay
    setTimeout(() => {
      setBusy(false);
      toast.error("Creación de cuenta restringida", {
        description: "El registro automático está deshabilitado por seguridad. Contacta al administrador para habilitar tu cuenta.",
      });
    }, 1500);
  }

  return (
    <main className="grid min-h-svh bg-[#160430] lg:grid-cols-2 text-zinc-100 font-sans">
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px) rotate(0deg); }
          50% { transform: translateY(-15px) rotate(2deg); }
        }
        .animate-float { animation: float 8s ease-in-out infinite; }
        
        @keyframes float-reverse {
          0%, 100% { transform: translateY(0px) rotate(0deg); }
          50% { transform: translateY(15px) rotate(-2deg); }
        }
        .animate-float-reverse { animation: float-reverse 10s ease-in-out infinite; }

        @keyframes twinkle {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.2); }
        }
        .animate-twinkle { animation: twinkle 4s ease-in-out infinite; }
        .animate-twinkle-delayed { animation: twinkle 5s ease-in-out infinite 2s; }
      `}</style>

      {/* Sección Izquierda: Ilustración Espacial */}
      <section className="relative hidden overflow-hidden bg-[#160430] lg:flex lg:flex-col lg:items-center lg:justify-center">
        {/* Generando el planeta y fondo espacial con Tailwind y radial-gradients */}
        <div className="absolute inset-0 z-0 overflow-hidden">
          <div className="absolute inset-0 animate-float">
            {/* Planeta Principal */}
            <div className="absolute top-[5%] left-[-15%] size-200 rounded-full bg-linear-to-tr from-[#3bf8ff] via-[#3a6bc0] to-[#160430] opacity-90 blur-[2px]" />
            <div className="absolute top-[5%] left-[-15%] size-200 rounded-full shadow-[inset_-40px_-40px_120px_rgba(22,4,48,0.95)]" />
          </div>

          {/* Textura sutil en el planeta (simulando ondas) */}
          <div className="absolute top-[20%] left-[-5%] w-150 h-37.5 bg-white/5 blur-2xl rounded-[100%]" />
          <div className="absolute top-[40%] left-[-10%] w-175 h-50 bg-white/5 blur-3xl rounded-[100%]" />

          {/* Planeta pequeño (Luna) */}
          <div className="absolute inset-0 animate-float-reverse">
            <div className="absolute top-[40%] left-[30%] size-45 rounded-full bg-linear-to-bl from-[#ae69ff] to-[#3b2063] blur-[1px] shadow-[inset_-15px_-15px_30px_rgba(22,4,48,0.8)]" />
          </div>

          {/* Anillos / Satélites sutiles */}
          <div className="absolute top-[30%] left-[10%] size-87.5 rounded-[100%] border border-white/10 rotate-[-15deg] scale-y-50" />
          <div className="absolute top-[30%] left-[5%] size-112.5 rounded-[100%] border border-white/5 rotate-[-15deg] scale-y-50" />

          {/* Luz difusa trasera */}
          <div className="absolute top-[50%] left-[30%] size-62.5 rounded-full bg-linear-to-br from-purple-500/20 to-transparent blur-3xl" />

          {/* Estrellas simples (dots) y estrellas fugaces */}
          <div className="absolute top-[20%] left-[60%] size-0.75 rounded-full bg-white shadow-[0_0_10px_white] animate-twinkle" />
          <div className="absolute top-[70%] left-[80%] size-2 rounded-full bg-white/80 shadow-[0_0_15px_white] animate-twinkle-delayed" />
          <div className="absolute top-[85%] left-[40%] size-1.5 rounded-full bg-white/60 shadow-[0_0_8px_white] animate-twinkle" />
          <div className="absolute top-[15%] left-[85%] size-0.5 rounded-full bg-purple-300 shadow-[0_0_10px_purple] animate-twinkle-delayed" />
          <div className="absolute top-[45%] left-[90%] size-1.5 rounded-full bg-cyan-200/50 shadow-[0_0_20px_cyan] animate-twinkle" />
          <div className="absolute top-[60%] left-[15%] size-1 rounded-full bg-white/70 shadow-[0_0_10px_white] animate-twinkle-delayed" />
          <div className="absolute top-[30%] left-[80%] size-1.5 rounded-full bg-blue-300/80 shadow-[0_0_15px_blue] animate-twinkle" />

          {/* Estrellas fugaces simuladas con rotación y escala */}
          <div className="absolute top-[10%] left-[50%] w-37.5 h-px bg-linear-to-r from-white to-transparent rotate-45 opacity-60" />
          <div className="absolute top-[75%] left-[25%] w-25 h-px bg-linear-to-r from-purple-400 to-transparent rotate-35 opacity-70" />
        </div>

        <div className="relative z-10 w-full max-w-lg px-12 text-left mt-auto pb-24 animate-in fade-in slide-in-from-left-8 duration-1000">
          <h1 className="text-[50px] font-bold leading-tight uppercase tracking-wide text-white">
            Sign in to your <br />
            <span className="text-transparent bg-clip-text bg-linear-to-br from-[#501794] to-[#ae69ff]">
              adventure!
            </span>
          </h1>
        </div>
      </section>

      {/* Sección Derecha: Formulario */}
      <section className="relative flex flex-col justify-center px-6 py-12 sm:px-12 lg:px-24 bg-[#160430]">

        {/* Header con el Logo */}
        <div className="absolute top-8 left-8 sm:top-12 sm:left-12 flex items-center gap-3">
          <div className="relative flex size-10 items-center justify-center">
            <NexaMascot mood="stable" size="mark" />
          </div>
          <div className="flex flex-col">
            <span className="text-2xl font-bold tracking-tight text-white leading-none">StreamML</span>
            <span className="text-[10px] uppercase tracking-[0.2em] text-[#a4a4a4] font-medium">Nexa</span>
          </div>
        </div>

        <div className="w-full max-w-115 mx-auto mt-16 lg:mt-0 animate-in fade-in slide-in-from-bottom-8 duration-1000 fill-mode-both delay-300">
          <h2 className="text-[54px] sm:text-[64px] font-bold text-white mb-2 leading-none uppercase tracking-tight">Sign In</h2>
          <p className="text-base font-bold text-white mb-8">Sign in with email address</p>

          <Tabs defaultValue="login" className="w-full">
            <TabsList className="grid w-full grid-cols-2 mb-8 h-12 rounded-xl p-1 bg-[#261046]/50 backdrop-blur-md border border-white/5">
              <TabsTrigger value="login" className="rounded-lg text-sm font-semibold transition-all data-[state=active]:bg-[#3b2063] data-[state=active]:text-white text-zinc-400">
                Iniciar Sesión
              </TabsTrigger>
              <TabsTrigger value="register" className="rounded-lg text-sm font-semibold transition-all data-[state=active]:bg-[#3b2063] data-[state=active]:text-white text-zinc-400">
                Registrarse
              </TabsTrigger>
            </TabsList>

            {/* LOGIN TAB */}
            <TabsContent value="login" className="animate-in fade-in zoom-in-95 duration-300 outline-none">
              <form onSubmit={handleLogin} className="grid gap-5">
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-4 pointer-events-none">
                    <Mail className="size-5 text-[#a4a4a4]" />
                  </div>
                  <Input
                    id="email"
                    type="email"
                    placeholder="Yourname@gmail.com"
                    autoComplete="username"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                    disabled={busy}
                    className="pl-12 h-17 rounded-[10px] border-none bg-[#261046]/80 backdrop-blur-md text-[#a4a4a4] placeholder:text-[#a4a4a4]/60 focus-visible:ring-2 focus-visible:ring-purple-500/50 shadow-[inset_0px_0px_11px_0px_rgba(0,0,0,0.16)] text-[16px]"
                  />
                </div>

                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-4 pointer-events-none">
                    <LockKeyhole className="size-5 text-[#a4a4a4]" />
                  </div>
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="Tu contraseña"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    disabled={busy}
                    className="pl-12 pr-12 h-17 rounded-[10px] border-none bg-[#261046]/80 backdrop-blur-md text-[#a4a4a4] placeholder:text-[#a4a4a4]/60 focus-visible:ring-2 focus-visible:ring-purple-500/50 shadow-[inset_0px_0px_11px_0px_rgba(0,0,0,0.16)] text-[16px]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((visible) => !visible)}
                    className="absolute right-2 top-1/2 flex size-10 -translate-y-1/2 items-center justify-center rounded-md text-[#a4a4a4] hover:text-white transition-colors"
                  >
                    {showPassword ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
                  </button>
                </div>

                {error ? (
                  <Alert variant="destructive" className="rounded-[10px] border-red-500/30 bg-red-500/10"><AlertDescription className="text-sm font-medium text-red-200">{error}</AlertDescription></Alert>
                ) : null}

                <Button type="submit" size="lg" className="mt-2 w-full h-15.5 rounded-[18px] text-[22px] font-medium text-white transition-all hover:opacity-90 shadow-lg" style={{ backgroundImage: "linear-gradient(90.27deg, rgb(80, 23, 148) 0%, rgb(62, 112, 161) 101.88%)" }} disabled={busy}>
                  {busy ? <><LoaderCircle className="animate-spin mr-2 size-5" />Accediendo…</> : "Sign up"}
                </Button>
              </form>
            </TabsContent>

            {/* REGISTER TAB */}
            <TabsContent value="register" className="animate-in fade-in zoom-in-95 duration-300 outline-none">
              <form onSubmit={handleRegister} className="grid gap-5">
                <div className="relative">
                  <Input
                    id="reg-name"
                    placeholder="Nombre completo"
                    value={registerName}
                    onChange={(e) => setRegisterName(e.target.value)}
                    required
                    disabled={busy}
                    className="px-6 h-14 rounded-[10px] border-none bg-[#261046]/80 backdrop-blur-md text-[#a4a4a4] placeholder:text-[#a4a4a4]/60 focus-visible:ring-2 focus-visible:ring-purple-500/50 shadow-[inset_0px_0px_11px_0px_rgba(0,0,0,0.16)] text-[16px]"
                  />
                </div>
                <div className="relative">
                  <Input
                    id="reg-email"
                    type="email"
                    placeholder="Correo electrónico"
                    value={registerEmail}
                    onChange={(e) => setRegisterEmail(e.target.value)}
                    required
                    disabled={busy}
                    className="px-6 h-14 rounded-[10px] border-none bg-[#261046]/80 backdrop-blur-md text-[#a4a4a4] placeholder:text-[#a4a4a4]/60 focus-visible:ring-2 focus-visible:ring-purple-500/50 shadow-[inset_0px_0px_11px_0px_rgba(0,0,0,0.16)] text-[16px]"
                  />
                </div>
                <div className="relative">
                  <Input
                    id="reg-password"
                    type="password"
                    placeholder="Contraseña"
                    value={registerPassword}
                    onChange={(e) => setRegisterPassword(e.target.value)}
                    required
                    disabled={busy}
                    className="px-6 h-14 rounded-[10px] border-none bg-[#261046]/80 backdrop-blur-md text-[#a4a4a4] placeholder:text-[#a4a4a4]/60 focus-visible:ring-2 focus-visible:ring-purple-500/50 shadow-[inset_0px_0px_11px_0px_rgba(0,0,0,0.16)] text-[16px]"
                  />
                </div>
                <div className="relative">
                  <Input
                    id="reg-confirm"
                    type="password"
                    placeholder="Confirmar Contraseña"
                    value={registerConfirm}
                    onChange={(e) => setRegisterConfirm(e.target.value)}
                    required
                    disabled={busy}
                    className="px-6 h-14 rounded-[10px] border-none bg-[#261046]/80 backdrop-blur-md text-[#a4a4a4] placeholder:text-[#a4a4a4]/60 focus-visible:ring-2 focus-visible:ring-purple-500/50 shadow-[inset_0px_0px_11px_0px_rgba(0,0,0,0.16)] text-[16px]"
                  />
                </div>

                {error ? (
                  <Alert variant="destructive" className="rounded-[10px] border-red-500/30 bg-red-500/10"><AlertDescription className="text-sm font-medium text-red-200">{error}</AlertDescription></Alert>
                ) : null}

                <Button type="submit" size="lg" className="mt-2 w-full h-15.5 rounded-[18px] text-[20px] font-medium text-white transition-all hover:opacity-90 shadow-lg" style={{ backgroundImage: "linear-gradient(90.27deg, rgb(80, 23, 148) 0%, rgb(62, 112, 161) 101.88%)" }} disabled={busy}>
                  {busy ? <><LoaderCircle className="animate-spin mr-2 size-5" />Registrando…</> : <><UserPlus className="mr-2 size-5" />Crear cuenta</>}
                </Button>
              </form>
            </TabsContent>
          </Tabs>

          <div className="mt-8 pt-8 border-t border-white/5 flex flex-col items-center">
            <p className="text-xs font-medium text-[#b6b6b6]">
              By registering you with our <span className="text-[#9d5ce9] hover:underline cursor-pointer">Terms and Conditions</span>
            </p>
          </div>

        </div>
      </section>
    </main>
  );
}
