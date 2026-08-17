import type { ReactNode } from "react";
import { statusLabel, toneForStatus, type Tone } from "../../utils/format";

export function Badge({
  children,
  tone,
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  const cls = tone ?? "neutral";
  return <span className={`badge badge-${cls}`}>{children}</span>;
}

/** Status badge: derives its tone from the backend status string. */
export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={toneForStatus(status)}>{statusLabel(status)}</Badge>;
}
