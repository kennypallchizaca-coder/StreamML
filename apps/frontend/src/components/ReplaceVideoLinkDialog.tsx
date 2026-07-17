import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "./ui/dialog";
import { Button } from "./ui/button";
import { Link2 } from "lucide-react";
import ExistingVideoLinkForm from "./ExistingVideoLinkForm";

interface ReplaceVideoLinkDialogProps {
  onLinkUpdated: (newUrl: string) => void;
}

export default function ReplaceVideoLinkDialog({ onLinkUpdated }: ReplaceVideoLinkDialogProps) {
  const [open, setOpen] = useState(false);
  const [validatedUrl, setValidatedUrl] = useState<string | null>(null);

  const handleUpdate = () => {
    if (validatedUrl) {
      onLinkUpdated(validatedUrl);
      setOpen(false);
      setValidatedUrl(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => {
      setOpen(o);
      if (!o) setValidatedUrl(null);
    }}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2 font-medium hover:bg-primary/10 hover:text-primary hover:border-primary/50 transition-colors">
          <Link2 className="size-4" />
          Cambiar enlace
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto border-border/60 p-0 sm:max-w-2xl">
        <DialogHeader className="p-5 pb-0 text-left sm:p-7 sm:pb-0">
          <DialogTitle className="text-xl font-semibold tracking-tight sm:text-2xl">Cambiar enlace de video</DialogTitle>
          <DialogDescription className="mt-2 text-sm leading-6 sm:text-base">
            Pega un nuevo enlace de VDO.Ninja si experimentas problemas graves o si cambiaste de dispositivo. 
            La telemetría continuará ejecutándose en segundo plano sin interrupciones.
          </DialogDescription>
        </DialogHeader>
        
        <div className="bg-muted/20 px-5 py-5 sm:px-7 sm:py-6">
          <ExistingVideoLinkForm 
            onValidatedLink={setValidatedUrl} 
            onContinue={handleUpdate} 
          />
        </div>

      </DialogContent>
    </Dialog>
  );
}
