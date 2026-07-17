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

  const handleCopy = async () => {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Error al copiar al portapapeles", err);
      // Fallback
      const textArea = document.createElement("textarea");
      textArea.value = link;
      document.body.appendChild(textArea);
      textArea.select();
      try {
        document.execCommand('copy');
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch (err) {
        console.error('Fallback: Oops, unable to copy', err);
      }
      document.body.removeChild(textArea);
    }
  };

  return (
    <Button 
      variant={copied ? "outline" : variant} 
      onClick={handleCopy} 
      disabled={!link}
      className={className}
    >
      {copied ? <Check className="mr-2 size-4 text-green-500" /> : <Copy className="mr-2 size-4" />}
      {copied ? "¡Copiado!" : label}
    </Button>
  );
}
