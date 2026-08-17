import type { ReactNode } from "react";
import { useProfile } from "../context/ProfileContext";
import { EmptyState, ErrorState, PageLoader } from "./ui/StateBox";

/**
 * Wraps pages that need the stored profile. Handles the loading,
 * profile-not-found and unverified states so each page can focus on
 * its own content. `requireVerified` is used by readiness /
 * prediction / eligibility / assessment pages (Phase 12-17 engines
 * reject unverified profiles).
 */
export function ProfileGate({
  children,
  requireVerified = false,
}: {
  children: (args: { profileId: string }) => ReactNode;
  requireVerified?: boolean;
}) {
  const { loading, error, exists, profile, refresh, profileId } = useProfile();

  if (loading) return <PageLoader />;

  if (error && !exists) {
    return (
      <ErrorState
        error={null}
        onRetry={() => void refresh()}
      />
    );
  }

  if (error) {
    return <div className="notice notice-warning">{error}</div>;
  }

  if (!exists) {
    return (
      <EmptyState icon="👤" title="No profile yet">
        <p>
          Create a demo profile first so the dashboard has data to show:
        </p>
        <code style={{ fontSize: 12 }}>python backend/scripts/seed_demo_profile.py</code>
        <button className="btn" onClick={() => void refresh()}>
          Retry
        </button>
      </EmptyState>
    );
  }

  if (requireVerified && !profile?.verified) {
    return (
      <EmptyState icon="🔒" title="Profile not verified">
        <p>
          This section needs a <strong>verified</strong> profile. Open the
          Profile page, review the extracted information and confirm it.
        </p>
      </EmptyState>
    );
  }

  return <>{children({ profileId })}</>;
}
