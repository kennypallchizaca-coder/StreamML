interface CircularGaugeProps {
  value: number;
  label: string;
  sublabel?: string;
  size?: number;
  strokeWidth?: number;
  color?: string;
  unit?: string;
}

export default function CircularGauge({
  value,
  label,
  sublabel,
  size = 150,
  strokeWidth = 8,
  color = "var(--primary)",
  unit = "%",
}: CircularGaugeProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  // Arc represents roughly 75% of the circle, rotated to bottom open
  const arcLength = circumference * 0.75;
  const tickCount = 12;
  const tickRadius = radius + 4;
  const safeValue = Math.min(100, Math.max(0, value));

  return (
    <div className="mx-auto flex flex-col items-center gap-3 text-center" style={{ width: size }}>
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="absolute inset-0 rotate-[135deg]"
          aria-hidden="true"
        >
        {/* SVG glow filter */}
        <defs>
          <filter id={`gauge-glow-${label}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Tick marks */}
        {Array.from({ length: tickCount }, (_, i) => {
          const angle = (i / tickCount) * (270) * (Math.PI / 180);
          const x1 = size / 2 + Math.cos(angle) * (tickRadius - 6);
          const y1 = size / 2 + Math.sin(angle) * (tickRadius - 6);
          const x2 = size / 2 + Math.cos(angle) * tickRadius;
          const y2 = size / 2 + Math.sin(angle) * tickRadius;
          return (
            <line
              key={i}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="currentColor"
              className="text-border/70"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          );
        })}

        {/* Background track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          className="text-muted"
          strokeWidth={strokeWidth}
          strokeDasharray={`${arcLength} ${circumference}`}
          strokeLinecap="round"
        />

        {/* Progress arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={`${arcLength} ${circumference}`}
          strokeDashoffset={arcLength - (safeValue / 100) * arcLength}
          strokeLinecap="round"
          filter={`url(#gauge-glow-${label})`}
          style={{ transition: "stroke-dashoffset 0.6s cubic-bezier(0.16, 1, 0.3, 1)" }}
        />
        </svg>

        <div className="relative z-10 -mt-2 flex flex-col items-center">
          <strong className="text-4xl font-semibold tabular-nums tracking-tight text-foreground">
            {safeValue}
          </strong>
          <span className="mt-1 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">{unit}</span>
        </div>
      </div>

      <div className="min-h-10">
        <div className="text-xs font-semibold uppercase tracking-[0.14em]" style={{ color }}>{label}</div>
        {sublabel ? <div className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">{sublabel}</div> : null}
      </div>
    </div>
  );
}
