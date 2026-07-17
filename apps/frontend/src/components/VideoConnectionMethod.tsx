import { useState } from "react";
import { Button } from "./ui/button";
import { Radio, Link2 } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import VideoPreview from "./VideoPreview";
import ExistingVideoLinkForm from "./ExistingVideoLinkForm";
import CopyLinkButton from "./CopyLinkButton";

interface VideoConnectionMethodProps {
  safePhoneUrl: string | null;
  embedUrl: string | null;
  onContinue: () => void;
  onLinkUpdated: (newUrl: string) => Promise<void> | void;
}

type MethodType = "new" | "existing";

export default function VideoConnectionMethod({ safePhoneUrl, embedUrl, onContinue, onLinkUpdated }: VideoConnectionMethodProps) {
  const [method, setMethod] = useState<MethodType>("new");

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
        <Button 
          variant={method === "new" ? "default" : "outline"}
          className={`h-auto min-h-28 py-5 flex flex-col gap-2.5 transition-all ${method === "new" ? "border-primary bg-primary/10 text-primary hover:bg-primary/15 ring-2 ring-primary/10" : "hover:border-primary/50"}`}
          onClick={() => setMethod("new")}
        >
          <Radio className="size-8" />
          <span className="font-semibold text-base">Crear una conexión nueva</span>
        </Button>
        <Button 
          variant={method === "existing" ? "default" : "outline"}
          className={`h-auto min-h-28 py-5 flex flex-col gap-2.5 transition-all ${method === "existing" ? "border-primary bg-primary/10 text-primary hover:bg-primary/15 ring-2 ring-primary/10" : "hover:border-primary/50"}`}
          onClick={() => setMethod("existing")}
        >
          <Link2 className="size-8" />
          <span className="font-semibold text-base">Usar un enlace existente</span>
        </Button>
      </div>

      <div className="border-t border-border/70 pt-6">
        {method === "new" && (
          <div className="grid gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500 lg:grid-cols-2">
            <div className="flex flex-col items-center gap-5 rounded-2xl border border-border/70 bg-muted/10 p-5 text-center sm:p-7">
              {safePhoneUrl ? (
                <>
                  <div className="rounded-2xl bg-white p-4 shadow-md ring-1 ring-black/5 sm:p-5">
                    <QRCodeSVG value={safePhoneUrl} size={184} level="M" />
                  </div>
                  <div className="space-y-2">
                    <h4 className="font-bold text-lg tracking-tight">Escanea este código</h4>
                    <p className="text-sm text-muted-foreground max-w-62.5 mx-auto leading-relaxed">Abre la cámara de tu teléfono y apunta al código para conectar.</p>
                  </div>
                  <CopyLinkButton link={safePhoneUrl} label="Copiar enlace para el teléfono" variant="outline" className="mt-2 w-full max-w-60" />
                </>
              ) : (
                <div className="text-center text-muted-foreground p-12">
                  <p className="font-semibold text-foreground text-lg">Conexión no disponible</p>
                  <p className="text-sm mt-2">No se pudo generar el enlace seguro.</p>
                </div>
              )}
            </div>
            
            <div className="flex min-w-0 flex-col gap-4">
              <VideoPreview embedUrl={embedUrl || ""} />
            </div>
          </div>
        )}

        {method === "existing" && (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            <ExistingVideoLinkForm 
              onContinue={async (url) => {
                await onLinkUpdated(url);
                onContinue();
              }}
            />
          </div>
        )}
      </div>

      {method === "new" && (
        <div className="flex justify-end pt-1">
          <Button size="lg" className="w-full px-8 sm:w-auto" onClick={onContinue}>Continuar al paso 3</Button>
        </div>
      )}
    </div>
  );
}
