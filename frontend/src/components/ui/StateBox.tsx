import type { ReactNode } from "react";
import { errorMessage } from "../../hooks/useApi";
import type { ApiError } from "../../types";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="state-box">
      <div className="spinner" />
      {label && <p>{label}</p>}
    </div>
  );
}

export function EmptyState({
  icon = "🗂️",
  title,
  children,
}: {
  icon?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="state-box">
      <div className="state-icon">{icon}</div>
      <h3>{title}</h3>
      {children}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: ApiError | null;
  onRetry?: () => void;
}) {
  return (
    <div className="state-box">
      <div className="state-icon">⚠️</div>
      <h3>Something went wrong</h3>
      <p>{errorMessage(error)}</p>
      {onRetry && (
        <button className="btn" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

/** Skeleton loading blocks for cards. */
export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="card">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 14, marginBottom: 10, width: i === lines - 1 ? "60%" : "100%" }} />
      ))}
    </div>
  );
}

export function PageLoader() {
  return (
    <div className="grid grid-2" style={{ marginTop: 8 }}>
      <SkeletonCard />
      <SkeletonCard />
      <SkeletonCard />
      <SkeletonCard />
    </div>
  );
}
