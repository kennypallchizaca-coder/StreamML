import { useState } from "react";
import { validateVdoNinjaLink, ValidationResult } from "../lib/VideoLinkValidator";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Alert, AlertDescription, AlertTitle } from "./ui/alert";
import { Link2, AlertTriangle, CheckCircle2 } from "@/components/icons";
import CopyLinkButton from "./CopyLinkButton";
import VideoPreview from "./VideoPreview";

interface ExistingVideoLinkFormProps {
  onContinue: (url: string) => Promise<void> | void;
}

export default function ExistingVideoLinkForm({ onContinue }: ExistingVideoLinkFormProps) {
  const [linkInput, setLinkInput] = useState("");
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleCheck = () => {
    const result = validateVdoNinjaLink(linkInput);
    setValidation(result);
    setSaveError(null);
  };

  const handleContinue = async () => {
    if (!validation?.isValid || !validation.sanitizedUrl) return;
    setSaving(true);
    setSaveError(null);
    try {
      await onContinue(validation.sanitizedUrl);
    } catch (reason) {
      setSaveError(reason instanceof Error ? reason.message : "No pudimos guardar el enlace de video.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="space-y-5">
        <div className="relative overflow-hidden rounded-2xl border border-border/70 bg-muted/10 p-5 sm:p-6">
          <div className="absolute top-0 left-0 w-1 h-full bg-primary/50"></div>
          <p className="text-sm font-medium mb-4 text-foreground/90">Pega aquí el enlace que VDO.Ninja te proporcionó para ver el video.</p>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Link2 className="absolute left-3.5 top-3 size-5 text-muted-foreground/60" />
              <Input 
                value={linkInput}
                onChange={(e) => setLinkInput(e.target.value)}
                placeholder="https://vdo.ninja/?view=..."
                className="h-12 rounded-xl border-border/70 bg-background pl-11 text-base focus-visible:ring-primary/30"
              />
            </div>
            <Button size="lg" className="h-12 rounded-xl px-6" onClick={handleCheck} disabled={!linkInput.trim()}>
              Comprobar enlace
            </Button>
          </div>
        </div>

        {validation && (
          <Alert variant={validation.isError ? "destructive" : "default"} className={`rounded-xl border-l-4 ${!validation.isError ? "border-success/50 bg-success-muted text-success-foreground" : "border-destructive/50"}`}>
            {validation.isError ? <AlertTriangle className="size-5" /> : <CheckCircle2 className="size-5 text-success" />}
            <AlertTitle className="text-base font-semibold">{validation.isError ? "Atención" : "Enlace válido"}</AlertTitle>
            <AlertDescription className="text-sm opacity-90 mt-1 leading-relaxed">{validation.message}</AlertDescription>
          </Alert>
        )}
      </div>

      {validation?.isValid && validation.sanitizedUrl && (
        <div className="space-y-6 rounded-2xl border border-border/70 bg-background p-5 shadow-sm animate-in fade-in zoom-in-95 duration-500 sm:p-6">
          <div className="ring-1 ring-border/50 rounded-xl overflow-hidden bg-media-background">
            <VideoPreview embedUrl={validation.sanitizedUrl} />
          </div>
          
          <div className="flex flex-col sm:flex-row gap-4 pt-4 border-t border-border/50 justify-end items-center">
            <CopyLinkButton link={validation.sanitizedUrl} variant="outline" className="w-full sm:w-auto h-11 px-6 rounded-xl" />
            <Button onClick={() => void handleContinue()} size="lg" className="w-full sm:w-auto h-11 px-8 rounded-xl font-semibold" disabled={saving}>
              {saving ? "Guardando…" : "Guardar y continuar"}
            </Button>
          </div>
          {saveError ? <Alert variant="destructive"><AlertTitle>No se pudo guardar el enlace</AlertTitle><AlertDescription>{saveError}</AlertDescription></Alert> : null}
        </div>
      )}
    </div>
  );
}
