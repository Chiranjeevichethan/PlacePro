/**
 * Shared student profile provider (single source of truth).
 *
 * The backend profile (GET /api/profile/{id}) is loaded ONCE here and every
 * page reads it through useStudentProfileContext():
 *
 *   - profileId  -> the current student's profile id (restored from
 *                   localStorage; switches after a resume is verified)
 *   - profile    -> flattened profile or null while loading/failed
 *   - loading / error / refetch / applyUpdatedProfile
 *   - resumeDraft / setPendingResumeDraft / clearPendingResumeDraft
 *
 * No global-state library is introduced: this is the existing
 * useStudentProfile() hook exposed through a small React context so the
 * Dashboard, Student Profile, Placement and Salary pages cannot drift onto
 * different profile ids (e.g. the demo profile) or stale local copies.
 */
import { useStudentProfile } from "./useProfile";
import { StudentProfileContext } from "./useStudentProfileContext";

export function StudentProfileProvider({ children, accountId }) {
  const studentProfile = useStudentProfile(accountId);

  return (
    <StudentProfileContext.Provider value={studentProfile}>
      {children}
    </StudentProfileContext.Provider>
  );
}
