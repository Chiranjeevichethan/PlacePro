import type { ReactNode } from "react";

export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  return (
    <span className="tooltip" tabIndex={0}>
      {children}
      <span className="tooltip-text">{text}</span>
    </span>
  );
}
