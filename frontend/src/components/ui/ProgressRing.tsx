import type { Tone } from "../../utils/format";

export function ProgressRing({
  value,
  caption,
  size = 96,
  stroke = 8,
  tone = "info",
}: {
  value: number;
  caption?: string;
  size?: number;
  stroke?: number;
  tone?: Tone;
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, value));
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div className="ring" style={{ ["--ring-size" as string]: `${size}px` }}>
      <svg viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle className="bg" cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} />
        <circle
          className={`fg ${tone === "info" ? "" : tone}`}
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="ring-label">
        <span className="ring-value">{Math.round(clamped)}</span>
        {caption && <span className="ring-caption">{caption}</span>}
      </div>
    </div>
  );
}
