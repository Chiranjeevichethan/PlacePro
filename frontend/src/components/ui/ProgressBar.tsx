import type { Tone } from "../../utils/format";

export function ProgressBar({
  value,
  tone = "info",
}: {
  value: number;
  tone?: Tone;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="progress-track" role="progressbar" aria-valuenow={clamped} aria-valuemin={0} aria-valuemax={100}>
      <div className={`progress-fill ${tone === "info" ? "" : tone}`} style={{ width: `${clamped}%` }} />
    </div>
  );
}
