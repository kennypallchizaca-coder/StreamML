import { getNexaVisualState, type NexaMood, type NexaVisualState } from "../lib/nexa";

const moodLabels: Record<NexaMood, string> = {
  waiting: "En espera",
  observing: "Analizando",
  stable: "Estable",
  protecting: "Protegiendo",
  backup: "Respaldo activo",
  recovering: "Recuperando",
  attention: "Atención",
};

const visualLabels: Record<NexaVisualState, string> = {
  neutral: "neutral",
  thinking: "pensando",
  working: "trabajando",
  success: "éxito",
  error: "error",
};

interface NexaMascotProps {
  mood: NexaMood;
  size?: "mark" | "compact" | "hero";
  announce?: boolean;
  className?: string;
}

export default function NexaMascot({
  mood,
  size = "compact",
  announce = false,
  className = "",
}: NexaMascotProps) {
  const visualState = getNexaVisualState(mood);

  return (
    <div
      className={`nexa-mascot nexa-mascot-${size} nexa-mood-${mood} nexa-visual-${visualState} ${className}`.trim()}
      role={announce ? "status" : undefined}
      aria-live={announce ? "polite" : undefined}
      aria-label={announce ? `Nexa: ${moodLabels[mood]}` : undefined}
      data-mood={mood}
      data-visual-state={visualState}
    >
      <span className="nexa-signal" aria-hidden="true" />
      <img
        key={visualState}
        src={`/brand/nexa-${visualState}.webp`}
        alt={size === "mark" ? "Nexa" : `Nexa, agente adaptativo en estado ${visualLabels[visualState]}`}
        draggable="false"
        decoding="async"
        loading={size === "mark" ? "eager" : "lazy"}
        width="256"
        height="256"
      />
    </div>
  );
}
