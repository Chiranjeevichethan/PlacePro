import type { ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Card({ title, actions, children, className }: CardProps) {
  return (
    <div className={`card ${className ?? ""}`}>
      {(title || actions) && (
        <div className="card-title">
          <h3>{title}</h3>
          {actions && <div className="flex">{actions}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

export function CardSection({ children }: { children: ReactNode }) {
  return <div className="card-section">{children}</div>;
}
