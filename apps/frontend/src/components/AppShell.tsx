import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Activity, LayoutDashboard, Radio, Settings, Bell, HelpCircle, BrainCircuit, LogOut } from "lucide-react";
import { useAuth } from "../App";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "./ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { Separator } from "./ui/separator";

const navigation = [
  { to: "/dashboard", label: "Inicio", icon: LayoutDashboard },
  { to: "/sessions/new", label: "Nueva transmisión", icon: Radio },
  { to: "/history", label: "Historial", icon: Activity },
  { to: "/models", label: "Modelos", icon: BrainCircuit },
  { to: "/alerts", label: "Alertas", icon: Bell },
  { to: "/settings", label: "Configuración", icon: Settings },
  { to: "/help", label: "Ayuda", icon: HelpCircle },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const userLabel = user?.display_name || user?.email || "Admin";
  const userInitials = userLabel.substring(0, 2).toUpperCase();

  const currentRoute = location.pathname.startsWith("/sessions/") && location.pathname.endsWith("/live")
    ? "Monitoreo en vivo"
    : navigation.find(n => location.pathname === n.to || (n.to !== "/" && location.pathname.startsWith(n.to)))?.label || "Inicio";

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon" className="border-r-sidebar-border/80">
        <SidebarHeader className="border-b border-sidebar-border/70">
          <div className="flex min-h-16 items-center gap-3 px-2">
            <div className="flex aspect-square size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm shadow-primary/20">
              <Activity className="size-4.5" />
            </div>
            <div className="min-w-0 flex flex-col gap-0.5 leading-none">
              <span className="truncate font-semibold tracking-tight">StreamML</span>
              <span className="truncate text-[11px] text-muted-foreground">Adaptive Engine</span>
            </div>
          </div>
        </SidebarHeader>
        
        <SidebarContent className="px-2 py-4">
          <SidebarMenu className="gap-1">
            {navigation.map((item) => (
              <SidebarMenuItem key={item.to}>
                <SidebarMenuButton asChild isActive={location.pathname.startsWith(item.to)} tooltip={item.label}>
                  <NavLink to={item.to} className="min-h-9">
                    <item.icon />
                    <span>{item.label}</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarContent>

        <SidebarFooter className="border-t border-sidebar-border/70 p-2">
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton size="lg" className="rounded-xl data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground">
                    <Avatar className="h-8 w-8 rounded-lg">
                      <AvatarFallback className="rounded-lg">{userInitials}</AvatarFallback>
                    </Avatar>
                    <div className="grid flex-1 text-left text-sm leading-tight">
                      <span className="truncate font-semibold">{userLabel}</span>
                      <span className="truncate text-xs text-muted-foreground">{user?.email || "Local Session"}</span>
                    </div>
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg" side="right" align="end" sideOffset={4}>
                  <DropdownMenuLabel className="p-0 font-normal">
                    <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                      <Avatar className="h-8 w-8 rounded-lg">
                        <AvatarFallback className="rounded-lg">{userInitials}</AvatarFallback>
                      </Avatar>
                      <div className="grid flex-1 text-left text-sm leading-tight">
                        <span className="truncate font-semibold">{userLabel}</span>
                        <span className="truncate text-xs">{user?.email || "Local Session"}</span>
                      </div>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => void logout()} className="gap-2">
                    <LogOut className="size-4" />
                    Cerrar sesión
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <SidebarInset className="min-w-0 overflow-x-hidden bg-muted/20">
        <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b bg-background/90 px-3 backdrop-blur-md sm:px-5">
          <SidebarTrigger className="-ml-1 rounded-lg" />
          <Separator orientation="vertical" className="hidden h-5 sm:block" />
          <div className="min-w-0">
            <span className="hidden text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground sm:block">Espacio de trabajo</span>
            <h1 className="truncate text-sm font-semibold">{currentRoute}</h1>
          </div>
        </header>
        <main className="flex min-w-0 flex-1 flex-col overflow-x-hidden p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
