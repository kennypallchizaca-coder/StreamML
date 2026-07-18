import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  Bell,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  History,
  LayoutDashboard,
  LogOut,
  Moon,
  Plus,
  Radio,
  Search,
  Settings,
  Sun,
} from "@/components/icons";
import type { IconComponent } from "@/components/icons";
import { useAuth } from "../App";
import { api } from "../api";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Input } from "./ui/input";
import { Separator } from "./ui/separator";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from "./ui/sidebar";

interface NavigationItem {
  to: string;
  label: string;
  description: string;
  icon: IconComponent;
}

const navigationGroups: ReadonlyArray<{ label: string; items: ReadonlyArray<NavigationItem> }> = [
  {
    label: "Operación",
    items: [
      { to: "/dashboard", label: "Centro de control", description: "Estado general y actividad", icon: LayoutDashboard },
      { to: "/sessions/new", label: "Nueva transmisión", description: "Crear y preparar una sesión", icon: Radio },
      { to: "/history", label: "Historial", description: "Sesiones y resultados", icon: History },
    ],
  },
  {
    label: "Inteligencia",
    items: [
      { to: "/models", label: "Modelos ML", description: "Modelos reactivo y predictivo", icon: BrainCircuit },
      { to: "/alerts", label: "Alertas", description: "Eventos que requieren atención", icon: Bell },
    ],
  },
  {
    label: "Sistema",
    items: [
      { to: "/settings", label: "Configuración", description: "Cuenta, streaming y conector", icon: Settings },
      { to: "/help", label: "Ayuda", description: "Guías y solución de problemas", icon: CircleHelp },
    ],
  },
];

const allNavigation = navigationGroups.flatMap((group) => group.items);

function isRouteActive(pathname: string, route: string) {
  if (route === "/dashboard") return pathname === route;
  return pathname === route || pathname.startsWith(`${route}/`);
}

function SidebarNavigation() {
  const location = useLocation();
  const { isMobile, setOpenMobile } = useSidebar();

  function closeOnMobile() {
    if (isMobile) setOpenMobile(false);
  }

  return (
    <>
      {navigationGroups.map((group) => (
        <SidebarGroup key={group.label} className="px-2 py-2">
          <SidebarGroupLabel className="px-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/45">
            {group.label}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1">
              {group.items.map((item) => (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton
                    asChild
                    isActive={isRouteActive(location.pathname, item.to)}
                    tooltip={item.label}
                    className="h-10 rounded-lg px-3 text-sidebar-foreground/70 transition-colors hover:text-sidebar-foreground data-[active=true]:bg-sidebar-accent data-[active=true]:font-medium data-[active=true]:text-sidebar-accent-foreground"
                  >
                    <NavLink to={item.to} onClick={closeOnMobile}>
                      <item.icon />
                      <span>{item.label}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      ))}
    </>
  );
}

function GlobalSearch({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const normalized = query.trim().toLocaleLowerCase("es");
  const results = useMemo(
    () => allNavigation.filter((item) => !normalized || `${item.label} ${item.description}`.toLocaleLowerCase("es").includes(normalized)),
    [normalized],
  );

  function goTo(path: string) {
    navigate(path);
    setQuery("");
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[18%] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-xl">
        <DialogHeader className="sr-only">
          <DialogTitle>Buscar en StreamML</DialogTitle>
          <DialogDescription>Encuentra una sección del panel y navega directamente.</DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-3 border-b px-4">
          <Search className="size-4 text-muted-foreground" aria-hidden="true" />
          <Input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && results[0]) goTo(results[0].to);
            }}
            placeholder="Buscar panel, transmisión, modelos…"
            aria-label="Buscar una sección"
            className="h-14 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0 dark:bg-transparent"
          />
        </div>
        <div className="max-h-[22rem] overflow-y-auto p-2">
          {results.length ? (
            results.map((item) => (
              <button
                key={item.to}
                type="button"
                onClick={() => goTo(item.to)}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition-colors hover:bg-accent focus-visible:bg-accent focus-visible:outline-none"
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border bg-background text-muted-foreground">
                  <item.icon className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">{item.label}</span>
                  <span className="block truncate text-xs text-muted-foreground">{item.description}</span>
                </span>
                <ChevronRight className="size-4 text-muted-foreground" />
              </button>
            ))
          ) : (
            <p className="px-3 py-10 text-center text-sm text-muted-foreground">No encontramos una sección con ese nombre.</p>
          )}
        </div>
        <div className="border-t bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
          Presiona Enter para abrir el primer resultado.
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [searchOpen, setSearchOpen] = useState(false);
  const [themeBusy, setThemeBusy] = useState(false);
  const [themeError, setThemeError] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(() => document.documentElement.classList.contains("dark"));
  const userLabel = user?.display_name || user?.email || "Administrador";
  const userInitials = userLabel.substring(0, 2).toUpperCase();
  const currentRoute = location.pathname.startsWith("/sessions/") && location.pathname.endsWith("/live")
    ? "Monitoreo en vivo"
    : allNavigation.find((item) => isRouteActive(location.pathname, item.to))?.label || "Centro de control";

  useEffect(() => {
    function openSearch(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen((current) => !current);
      }
    }
    window.addEventListener("keydown", openSearch);
    return () => window.removeEventListener("keydown", openSearch);
  }, []);

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setDarkMode(document.documentElement.classList.contains("dark"));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!themeError) return;
    const timeout = window.setTimeout(() => setThemeError(null), 5000);
    return () => window.clearTimeout(timeout);
  }, [themeError]);

  async function toggleTheme() {
    const nextDarkMode = !darkMode;
    setThemeBusy(true);
    setThemeError(null);
    document.documentElement.classList.toggle("dark", nextDarkMode);
    setDarkMode(nextDarkMode);
    try {
      const settings = await api.getSettings();
      await api.updatePreferences({ ...settings.preferences, dark_mode: nextDarkMode });
    } catch {
      document.documentElement.classList.toggle("dark", darkMode);
      setDarkMode(darkMode);
      setThemeError("No pudimos guardar el tema. Revisa la conexión con la API e inténtalo nuevamente.");
    } finally {
      setThemeBusy(false);
    }
  }

  return (
    <SidebarProvider>
      <a href="#main-content" className="skip-link">Saltar al contenido principal</a>
      <Sidebar collapsible="icon" className="border-r-sidebar-border/80">
        <SidebarHeader className="border-b border-sidebar-border/70 p-3">
          <Link to="/dashboard" className="flex min-h-11 items-center gap-3 rounded-lg px-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring">
            <div className="relative flex size-9 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground shadow-sm">
              <Activity className="size-4.5" />
              <span className="absolute -right-0.5 -top-0.5 size-2.5 rounded-full border-2 border-sidebar bg-success" />
            </div>
            <div className="min-w-0 leading-none group-data-[collapsible=icon]:hidden">
              <span className="block truncate text-sm font-semibold tracking-tight">StreamML</span>
              <span className="mt-1 block truncate text-[10px] font-medium uppercase tracking-[0.15em] text-sidebar-foreground/45">Adaptive Control</span>
            </div>
          </Link>
        </SidebarHeader>

        <SidebarContent className="py-2">
          <SidebarNavigation />
        </SidebarContent>

        <SidebarFooter className="border-t border-sidebar-border/70 p-2">
          <div className="mb-2 rounded-lg border border-sidebar-border/70 bg-sidebar-accent/45 p-3 group-data-[collapsible=icon]:hidden">
            <div className="flex items-center gap-2 text-xs font-medium">
              <CheckCircle2 className="size-3.5 text-success" />
              Sesión protegida
            </div>
            <p className="mt-1 text-[11px] leading-4 text-sidebar-foreground/50">API autenticada y panel disponible.</p>
          </div>
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton size="lg" className="rounded-lg data-[state=open]:bg-sidebar-accent">
                    <Avatar className="h-8 w-8 rounded-lg">
                      <AvatarFallback className="rounded-lg bg-sidebar-primary text-xs text-sidebar-primary-foreground">{userInitials}</AvatarFallback>
                    </Avatar>
                    <div className="grid flex-1 text-left text-sm leading-tight">
                      <span className="truncate font-medium">{userLabel}</span>
                      <span className="truncate text-[11px] text-sidebar-foreground/50">{user?.email || "Sesión local"}</span>
                    </div>
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width] min-w-60 rounded-lg" side="right" align="end" sideOffset={6}>
                  <DropdownMenuLabel className="font-normal">
                    <p className="truncate text-sm font-medium">{userLabel}</p>
                    <p className="truncate text-xs text-muted-foreground">{user?.email || "Sesión local"}</p>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild><Link to="/settings"><Settings />Configuración</Link></DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => void logout()} className="gap-2 text-destructive focus:text-destructive">
                    <LogOut />Cerrar sesión
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <SidebarInset className="min-w-0 overflow-x-hidden bg-background">
        <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b bg-background/88 px-3 backdrop-blur-xl sm:px-5">
          <SidebarTrigger className="-ml-1 rounded-lg" aria-label="Abrir o cerrar navegación" />
          <Separator orientation="vertical" className="hidden h-5 sm:block" />
          <div className="min-w-0">
            <p className="hidden text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground sm:block">StreamML Workspace</p>
            <p className="truncate text-sm font-medium">{currentRoute}</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              className="hidden h-9 w-52 items-center gap-2 rounded-lg border bg-muted/35 px-3 text-sm text-muted-foreground transition-colors hover:bg-muted/70 md:flex"
            >
              <Search className="size-3.5" />
              <span className="flex-1 text-left">Buscar…</span>
              <kbd className="rounded border bg-background px-1.5 py-0.5 text-[10px] font-medium">Ctrl K</kbd>
            </button>
            <Button variant="ghost" size="icon-sm" className="md:hidden" onClick={() => setSearchOpen(true)} aria-label="Buscar en StreamML">
              <Search />
            </Button>
            <div className="hidden items-center gap-2 rounded-full border bg-muted/25 px-2.5 py-1.5 text-[11px] font-medium text-muted-foreground xl:flex">
              <span className="size-1.5 rounded-full bg-success shadow-[0_0_0_3px_color-mix(in_oklab,var(--success)_15%,transparent)]" />
              Panel conectado
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => void toggleTheme()}
              disabled={themeBusy}
              aria-label={darkMode ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
              title={darkMode ? "Tema claro" : "Tema oscuro"}
            >
              {darkMode ? <Sun /> : <Moon />}
            </Button>
            <Button size="sm" className="hidden gap-1.5 sm:inline-flex" asChild>
              <Link to="/sessions/new"><Plus />Nueva transmisión</Link>
            </Button>
          </div>
        </header>
        <main id="main-content" className="flex min-w-0 flex-1 flex-col overflow-x-hidden p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </SidebarInset>
      <GlobalSearch open={searchOpen} onOpenChange={setSearchOpen} />
      {themeError ? (
        <div role="alert" className="fixed bottom-4 right-4 z-50 max-w-sm rounded-lg border border-destructive/30 bg-background px-4 py-3 text-sm text-destructive shadow-xl">
          {themeError}
        </div>
      ) : null}
    </SidebarProvider>
  );
}
