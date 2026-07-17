import { useState } from "react";
import { Button } from "./ui/button";
import { Copy, Check } from "lucide-react";

interface CopyLinkButtonProps {
  link: string | null;
  label?: string;
  variant?: "default" | "outline" | "secondary" | "ghost" | "link";
  className?: string;
}

export default function CopyLinkButton({ link, label = "Copiar enlace para OBS", variant = "default", className }: CopyLinkButtonProps) {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);

  const showCopied = () => {
    setCopied(true);
    setCopyFailed(false);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopy = async () => {
    if (!link) return;
    setCopyFailed(false);
    try {
      await navigator.clipboard.writeText(link);
      showCopied();
    } catch {
      // Fallback
      const textArea = document.createElement("textarea");
      textArea.value = link;
      document.body.appendChild(textArea);
      textArea.select();
      try {
        if (!document.execCommand('copy')) throw new Error("Clipboard fallback failed.");
        showCopied();
      } catch {
        setCopyFailed(true);
        setTimeout(() => setCopyFailed(false), 3000);
      }
      document.body.removeChild(textArea);
    }
  };

  return (
    <Button 
      variant={copied || copyFailed ? "outline" : variant}
      onClick={handleCopy} 
      disabled={!link}
      className={className}
    >
      {copied ? <Check className="mr-2 size-4 text-green-500" /> : <Copy className="mr-2 size-4" />}
      {copied ? "¡Copiado!" : copyFailed ? "No se pudo copiar" : label}
    </Button>
  );
}
