import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Switch } from "../components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { useAuth } from "../App";
import { LogOut, User, Settings, Video, Link2, ShieldAlert } from "lucide-react";
import PageHeader from "../components/PageHeader";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const userName = user?.display_name || user?.email || "Admin";

  return (
    <div className="app-page max-w-5xl">
      <PageHeader eyebrow="Cuenta" title="Configuración" description="Administra tus preferencias de cuenta, transmisión y privacidad." />

      <Tabs defaultValue="account" className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-2 gap-1 rounded-xl p-1 sm:grid-cols-3 lg:grid-cols-5">
          <TabsTrigger value="account" className="gap-2"><User className="size-4" /> Cuenta</TabsTrigger>
          <TabsTrigger value="preferences" className="gap-2"><Settings className="size-4" /> Preferencias</TabsTrigger>
          <TabsTrigger value="stream" className="gap-2"><Video className="size-4" /> Transmisión</TabsTrigger>
          <TabsTrigger value="connections" className="gap-2"><Link2 className="size-4" /> Conexiones</TabsTrigger>
          <TabsTrigger value="privacy" className="gap-2"><ShieldAlert className="size-4" /> Privacidad</TabsTrigger>
        </TabsList>
        
        <TabsContent value="account" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Detalles de la cuenta</CardTitle>
              <CardDescription>Información básica de tu perfil en StreamML.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Nombre completo</Label>
                <Input defaultValue={userName} />
              </div>
              <div className="space-y-2">
                <Label>Correo electrónico</Label>
                <Input defaultValue={user?.email || "correo@ejemplo.com"} disabled />
              </div>
              <div className="space-y-2 pt-4">
                <Label>Cambiar contraseña</Label>
                <Input type="password" placeholder="Nueva contraseña" />
              </div>
              <div className="space-y-2">
                <Input type="password" placeholder="Confirmar nueva contraseña" />
              </div>
            </CardContent>
            <CardFooter className="flex flex-col-reverse items-stretch justify-between gap-3 border-t sm:flex-row sm:items-center">
              <Button variant="outline" onClick={() => void logout()} className="text-destructive hover:bg-destructive/10 hover:text-destructive">
                <LogOut className="mr-2 size-4" /> Cerrar sesión
              </Button>
              <Button>Guardar cambios</Button>
            </CardFooter>
          </Card>
        </TabsContent>

        <TabsContent value="preferences" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Preferencias generales</CardTitle>
              <CardDescription>Personaliza tu experiencia en la plataforma.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-0.5">
                  <Label>Idioma</Label>
                  <p className="text-sm text-muted-foreground">El idioma de la interfaz gráfica.</p>
                </div>
                <Select defaultValue="es">
                  <SelectTrigger className="w-full sm:w-48"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="es">Español</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-0.5">
                  <Label>Zona horaria</Label>
                  <p className="text-sm text-muted-foreground">Se utilizará para tus historiales.</p>
                </div>
                <Select defaultValue="auto">
                  <SelectTrigger className="w-full sm:w-48"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Automática</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <Label>Tema oscuro</Label>
                  <p className="text-sm text-muted-foreground">Activar colores oscuros para la interfaz.</p>
                </div>
                <Switch defaultChecked />
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-0.5">
                  <Label>Nivel de detalle de alertas</Label>
                  <p className="text-sm text-muted-foreground">Cantidad de consejos mostrados.</p>
                </div>
                <Select defaultValue="normal">
                  <SelectTrigger className="w-full sm:w-48"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Reducido</SelectItem>
                    <SelectItem value="normal">Normal</SelectItem>
                    <SelectItem value="high">Detallado</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="stream" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Ajustes por defecto</CardTitle>
              <CardDescription>Valores predeterminados al crear nuevas transmisiones.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Resolución preferida</Label>
                <Select defaultValue="1080p">
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1080p">1080p (Alta definición)</SelectItem>
                    <SelectItem value="720p">720p (Estándar)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Calidad preferida</Label>
                <Select defaultValue="high">
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">Alta (Requiere mejor conexión)</SelectItem>
                    <SelectItem value="balanced">Equilibrada</SelectItem>
                    <SelectItem value="low">Básica (Máxima estabilidad)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Plataforma principal</Label>
                <Select defaultValue="youtube">
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="youtube">YouTube Live</SelectItem>
                    <SelectItem value="twitch">Twitch</SelectItem>
                    <SelectItem value="facebook">Facebook</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
            <CardFooter className="flex justify-stretch border-t sm:justify-end">
              <Button className="w-full sm:w-auto">Guardar preferencias</Button>
            </CardFooter>
          </Card>
        </TabsContent>

        <TabsContent value="connections" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Dispositivos conectados</CardTitle>
              <CardDescription>Administra los dispositivos que pueden transmitir datos.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex flex-col gap-4 rounded-xl border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h4 className="font-semibold">Teléfono móvil</h4>
                  <p className="text-sm text-muted-foreground">Cámara inalámbrica principal</p>
                </div>
                <div className="flex flex-col gap-2 sm:items-end">
                  <div className="text-sm text-green-500 font-medium hidden sm:block">Activo recientemente</div>
                  <Button variant="outline" size="sm">Volver a vincular</Button>
                </div>
              </div>

              <div className="flex flex-col gap-4 rounded-xl border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h4 className="font-semibold">Aplicación de transmisión</h4>
                  <p className="text-sm text-muted-foreground">Programa instalado en la computadora</p>
                </div>
                <div className="flex flex-col gap-2 sm:items-end">
                  <div className="text-sm text-amber-500 font-medium hidden sm:block">En espera</div>
                  <Button variant="outline" size="sm">Comprobar conexión</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="privacy" className="space-y-6 mt-6">
          <Card className="border-destructive/20">
            <CardHeader>
              <CardTitle className="text-destructive">Privacidad y Datos</CardTitle>
              <CardDescription>Gestiona tu información personal.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 border rounded-lg">
                <div>
                  <h4 className="font-semibold">Descargar mis datos</h4>
                  <p className="text-sm text-muted-foreground">Obtén una copia de tu historial y configuración.</p>
                </div>
                <Button variant="secondary" className="shrink-0">Descargar reporte</Button>
              </div>

              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 border rounded-lg border-destructive/20 bg-destructive/5">
                <div>
                  <h4 className="font-semibold text-destructive">Eliminar historial</h4>
                  <p className="text-sm text-destructive/80">Borra permanentemente todas tus transmisiones anteriores.</p>
                </div>
                <Button variant="destructive" className="shrink-0">Borrar historial</Button>
              </div>

              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 border rounded-lg border-destructive/20 bg-destructive/5">
                <div>
                  <h4 className="font-semibold text-destructive">Cerrar cuenta</h4>
                  <p className="text-sm text-destructive/80">Elimina tu cuenta y todos los datos asociados.</p>
                </div>
                <Button variant="destructive" className="shrink-0">Eliminar cuenta</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

      </Tabs>
    </div>
  );
}
