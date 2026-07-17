import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { HelpCircle, Smartphone, Video, Radio, Activity, AlertTriangle, MonitorPlay } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import PageHeader from "../components/PageHeader";

export default function HelpPage() {
  return (
    <div className="app-page max-w-5xl">
      <PageHeader eyebrow="Soporte" title="Centro de ayuda" description="Encuentra respuestas rápidas y guías paso a paso para usar StreamML sin complicaciones." />

      <div className="grid gap-6 md:grid-cols-2">
        {/* Guías rápidas */}
        <Card className="md:col-span-2 bg-primary/5 border-primary/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Radio className="size-5 text-primary" />Guía rápida: Iniciar una transmisión</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="list-decimal list-inside space-y-4 text-sm font-medium">
              <li className="p-3 bg-background rounded-lg border">Dirígete a la sección <strong>Nueva transmisión</strong> en el menú principal.</li>
              <li className="p-3 bg-background rounded-lg border">Escribe un nombre para identificar tu evento y elige la configuración.</li>
              <li className="p-3 bg-background rounded-lg border">Escanea el código QR en la pantalla con la cámara de tu teléfono.</li>
              <li className="rounded-lg border bg-background p-3">Abre OBS en la computadora y confirma visualmente que la fuente de video funciona.</li>
              <li className="rounded-lg border bg-background p-3">Abre el monitoreo; los estados reales aparecerán cuando lleguen video y telemetría.</li>
            </ol>
          </CardContent>
        </Card>

        {/* Teléfono */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Smartphone className="size-5 text-primary" />Cómo conectar el teléfono</CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-4 text-muted-foreground">
            <p>Usaremos la cámara de tu teléfono para capturar la imagen en tiempo real y enviarla a tu computadora.</p>
            <ul className="list-disc list-inside space-y-2">
              <li>Abre la aplicación de cámara de tu celular.</li>
              <li>Apunta al código QR que aparece al crear una transmisión.</li>
              <li>Toca el enlace que aparecerá en tu pantalla.</li>
              <li>Permite el uso de la cámara y el micrófono cuando el navegador te lo solicite.</li>
            </ul>
            <p className="font-semibold text-amber-500 mt-2">Importante: No bloquees la pantalla de tu teléfono mientras transmites.</p>
          </CardContent>
        </Card>

        {/* Aplicación */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><MonitorPlay className="size-5 text-primary" />Conectar aplicación de transmisión</CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-4 text-muted-foreground">
            <p>StreamML recibe telemetría de tu software de transmisión para mostrar recomendaciones que tú decides si aplicar.</p>
            <ul className="list-disc list-inside space-y-2">
              <li>Abre tu software de transmisión.</li>
              <li>Instala y vincula StreamML Connector con el código temporal de tu sesión.</li>
              <li>El conector solo lee estadísticas; nunca cambia la configuración de OBS.</li>
            </ul>
          </CardContent>
        </Card>
      </div>

      <h3 className="text-xl font-bold mt-4">Preguntas frecuentes y solución de problemas</h3>
      <div className="space-y-4 w-full">
        <div className="border rounded-lg p-4">
          <h4 className="font-semibold mb-2">¿Qué significan los estados de transmisión?</h4>
          <div className="space-y-4 text-muted-foreground">
            <div className="flex gap-2 items-center"><Badge className="bg-green-500">Excelente</Badge> Todo funciona a la perfección.</div>
            <div className="flex gap-2 items-center"><Badge className="bg-blue-500">Buena</Badge> Hay pequeñas variaciones normales en Internet.</div>
            <div className="flex gap-2 items-center"><Badge className="bg-amber-500">Inestable</Badge> Tu red tiene problemas. Podría haber retrasos.</div>
            <div className="flex gap-2 items-center"><Badge className="bg-destructive">Crítica</Badge> Riesgo alto de que la transmisión se corte.</div>
          </div>
        </div>
        <div className="border rounded-lg p-4">
          <h4 className="font-semibold mb-2">¿Qué hago si mi conexión es inestable?</h4>
          <div className="text-muted-foreground space-y-2">
            <p>Si StreamML te alerta de que la conexión es inestable:</p>
            <ol className="list-decimal list-inside space-y-1 pl-2">
              <li>Mantén abierto el conector para que pueda reconectarse cuando OBS o la API vuelvan a estar disponibles.</li>
              <li>Si estás usando Wi-Fi, acércate al router o usa un cable de red.</li>
              <li>Cierra otras aplicaciones que consuman Internet (descargas, otras transmisiones).</li>
              <li>Sigue las recomendaciones que aparezcan en la pantalla principal.</li>
            </ol>
          </div>
        </div>
        <div className="border rounded-lg p-4">
          <h4 className="font-semibold mb-2">El teléfono se desconectó de repente</h4>
          <div className="text-muted-foreground">
            <p>Esto ocurre generalmente cuando el teléfono se bloquea automáticamente por inactividad, entra una llamada o te alejas demasiado del router Wi-Fi.</p>
            <p className="mt-2">Desbloquea el teléfono y vuelve a la pestaña del navegador para reconectar automáticamente.</p>
          </div>
        </div>
      </div>

      <Card className="mt-6 border-dashed bg-muted/10">
        <CardContent className="flex flex-col sm:flex-row items-center justify-between p-6 gap-4">
          <div>
            <h4 className="font-semibold">¿Necesitas más ayuda?</h4>
            <p className="text-sm text-muted-foreground">Nuestro equipo de soporte técnico está disponible para ayudarte.</p>
          </div>
          <Button>Contactar a soporte</Button>
        </CardContent>
      </Card>
    </div>
  );
}
