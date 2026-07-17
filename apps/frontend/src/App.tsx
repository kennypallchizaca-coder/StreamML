import { createContext, lazy, Suspense, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import AppShell from "./components/AppShell";
import type { UserSummary } from "./types";

const CreateStreamPage = lazy(() => import("./pages/CreateStreamPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const HistoryPage = lazy(() => import("./pages/HistoryPage"));
const LiveMonitorPage = lazy(() => import("./pages/LiveMonitorPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const ModelsPage = lazy(() => import("./pages/ModelsPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const HelpPage = lazy(() => import("./pages/HelpPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));

interface AuthContextValue {
  authenticated: boolean;
  user: UserSummary | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}

function ProtectedLayout() {
  const { authenticated } = useAuth();
  const location = useLocation();
  if (!authenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <AppShell />;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<UserSummary | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const navigate = useNavigate();

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password);
    setAuthenticated(true);
    setUser(response.user ?? { email });
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // El estado local se cierra aunque el servidor ya haya invalidado la cookie.
    } finally {
      setAuthenticated(false);
      setUser(null);
      navigate("/login", { replace: true });
    }
  }, [navigate]);

  useEffect(() => {
    const handleUnauthorized = () => {
      setAuthenticated(false);
      setUser(null);
      navigate("/login", { replace: true });
    };
    window.addEventListener("streamml:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("streamml:unauthorized", handleUnauthorized);
  }, [navigate]);

  useEffect(() => {
    let active = true;
    void api.me()
      .then((response) => {
        if (!active) return;
        setAuthenticated(true);
        setUser(response.user ?? null);
      })
      .catch(() => {
        if (!active) return;
        setAuthenticated(false);
        setUser(null);
      })
      .finally(() => { if (active) setCheckingAuth(false); });
    return () => { active = false; };
  }, []);

  const auth = useMemo(() => ({ authenticated, user, login, logout }), [authenticated, user, login, logout]);

  if (checkingAuth) {
    return <main className="route-loading" aria-live="polite">Verificando sesión…</main>;
  }

  return (
    <AuthContext.Provider value={auth}>
      <Suspense fallback={<main className="route-loading" aria-live="polite">Cargando StreamML…</main>}>
        <Routes>
          <Route path="/login" element={authenticated ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
          <Route element={<ProtectedLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/sessions/new" element={<CreateStreamPage />} />
            <Route path="/sessions/:sessionId/live" element={<LiveMonitorPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/help" element={<HelpPage />} />
          </Route>
          <Route path="/" element={<Navigate to={authenticated ? "/dashboard" : "/login"} replace />} />
          <Route path="*" element={<Navigate to={authenticated ? "/dashboard" : "/login"} replace />} />
        </Routes>
      </Suspense>
    </AuthContext.Provider>
  );
}
