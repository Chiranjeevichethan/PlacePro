import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Navbar from "./components/Navbar";
import { initialFormData as initialPredictionDraft } from "./data/formDefaults";
import Sidebar from "./components/Sidebar";

import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import CareerReadiness from "./pages/CareerReadiness";
import Prediction from "./pages/Prediction";
import ExperimentalV1Prediction from "./pages/ExperimentalV1Prediction";
import SalaryPrediction from "./pages/SalaryPrediction";
import CompanyRecommendations from "./pages/CompanyRecommendations";
import SkillGapAnalysis from "./pages/SkillGapAnalysis";
import MockTests from "./pages/MockTests";
import StudentProfile from "./pages/StudentProfile";
import PerformanceAnalysis from "./pages/PerformanceAnalysis";
import About from "./pages/About";
import NotificationCenter from "./pages/NotificationCenter.jsx";
import StudentResumeBuilder from "./pages/StudentResumeBuilder.jsx";

import { authSession, logout } from "./services/auth";
import { buildPredictionDraftFromProfile } from "./services/profileConfig";
import { StudentProfileProvider } from "./hooks/StudentProfileProvider";
import { useStudentProfileContext } from "./hooks/useStudentProfileContext";

import { useAuth } from './hooks/useAuth';
import ResumeUploadModal from './components/ResumeUploadModal';
import AccessibleModal from './components/AccessibleModal.jsx';
import ProfileJourneyNotice from './components/ProfileJourneyNotice';
import { isSyntheticDemo } from './services/studentJourney';
import { resumeDiagnosticInstance, traceResume } from './services/resumeDiagnostics.js';
import { focusMainContent } from './services/skipToContent.js';
import { fetchUnreadNotificationCount } from './services/goalsApi.js';
import { APP_ROUTES, appHrefForPage, appPageFromPath, appTitleForPage } from './services/appRoutes.js';
import "./App.css";

function AppContent() {
  const [currentPage, setCurrentPage] = useState(() => appPageFromPath(window.location.pathname) || "dashboard");
  const currentPageRef = useRef(currentPage);
  const assessmentStateRef = useRef({ active: false, dialogAvailable: false });
  const [showRouteLeaveConfirmation, setShowRouteLeaveConfirmation] = useState(false);
  const pendingNavigationRef = useRef(null);
  const [editProfileOpen, setEditProfileOpen] = useState(false);
  const [resumeProfileOpen, setResumeProfileOpen] = useState(false);
  const [resumeBuilderVisited, setResumeBuilderVisited] = useState(false);
  const [careerReadinessVisited, setCareerReadinessVisited] = useState(false);
  const [unreadNotificationCount, setUnreadNotificationCount] = useState(null);
  const [notificationTarget, setNotificationTarget] = useState(null);

  /* The ONE canonical student profile (loaded from the backend by the
     provider). Every page reads it through context; nothing keeps a second
     copy of the student's name/values. */
  const { profile, profileKey, profileId, rawProfile, error: profileError,
    completion, loading: profileLoading, resumeDraft, setPendingResumeDraft, clearPendingResumeDraft, refetch } = useStudentProfileContext();
  useEffect(() => {
    if (!profileId) return undefined;
    let active = true;
    const refresh = async () => {
      try {
        const result = await fetchUnreadNotificationCount(profileId);
        if (active) setUnreadNotificationCount(result.unread_count ?? null);
      } catch {
        if (active) setUnreadNotificationCount(null);
      }
    };
    const onGoalChange = () => { void refresh(); };
    const onVisibility = () => { if (document.visibilityState === 'visible') void refresh(); };
    void refresh();
    window.addEventListener('placepro-goals-changed', onGoalChange);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      active = false;
      window.removeEventListener('placepro-goals-changed', onGoalChange);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [profileId]);
  const [newProfileOpen, setNewProfileOpen] = useState(false);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const [logoutError, setLogoutError] = useState(null);
  const logoutInFlight = useRef(false);
  const [diagnosticId] = useState(resumeDiagnosticInstance);
  const previousResumeState = useRef(null);
  useEffect(() => {
    traceResume('app.mount', { instance: diagnosticId, source: 'AppContent' });
    return () => traceResume('app.unmount', { instance: diagnosticId, source: 'AppContent' });
  }, [diagnosticId]);
  useEffect(() => {
    traceResume('app.state', { instance: diagnosticId, source: 'AppContent.commit',
      previous: previousResumeState.current, next: resumeProfileOpen, open: resumeProfileOpen,
      page: currentPage, profileId: profileId || '', loading: profileLoading, profileError: Boolean(profileError) });
    previousResumeState.current = resumeProfileOpen;
  }, [diagnosticId, resumeProfileOpen, currentPage, profileId, profileLoading, profileError]);

  const commitNavigation = useCallback((page, historyMode = "push") => {
    const path = appHrefForPage(page);
    if (historyMode === "push") window.history.pushState({ placeProPage: page }, "", path);
    if (historyMode === "replace") window.history.replaceState({ placeProPage: page }, "", path);
    currentPageRef.current = page;
    setCurrentPage(page);
    if (page === "readiness" || page === "goals") setCareerReadinessVisited(true);
    if (page === "resume") setResumeBuilderVisited(true);
    if (page !== "profile") {
      setEditProfileOpen(false);
      setResumeProfileOpen(false);
    }
  }, []);

  const requestAssessmentLeaveConfirmation = useCallback(() => {
    if (assessmentStateRef.current.dialogAvailable) {
      window.dispatchEvent(new Event("placepro:request-assessment-leave"));
    } else {
      setShowRouteLeaveConfirmation(true);
    }
  }, []);

  useEffect(() => {
    const path = appHrefForPage(currentPage);
    if (`${window.location.pathname}${window.location.hash}` !== path) {
      window.history.replaceState({ placeProPage: currentPage }, "", path);
    }
    document.title = `${appTitleForPage(currentPage)} | PLACE PRO`;
    document.getElementById("main-content")?.focus({ preventScroll: true });
  }, [currentPage]);

  useEffect(() => {
    if (currentPage !== "goals" || window.location.hash !== "#goal-management") return;
    const heading = document.getElementById("goal-management-title");
    heading?.focus({ preventScroll: true });
    heading?.scrollIntoView({ block: "start" });
  }, [currentPage]);

  useEffect(() => {
    const onPopState = () => {
      const page = appPageFromPath(window.location.pathname);
      if (!page) {
        commitNavigation("dashboard", "replace");
        return;
      }
      if (page === currentPageRef.current) return;
      if (currentPageRef.current === "mocktests" && assessmentStateRef.current.active && page !== "mocktests") {
        pendingNavigationRef.current = { page, historyMode: "pop" };
        requestAssessmentLeaveConfirmation();
        return;
      }
      commitNavigation(page, "none");
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [commitNavigation, currentPage, requestAssessmentLeaveConfirmation]);

  /* Placement-form draft, derived from the shared profile.
     - Lives in App (above the page switch) so the user's in-progress form
       survives navigating to another page and returning.
     - The stored draft is stamped with the profile signature it was edited
       against. If the canonical profile changes (first load, resume
       verification, or an edit saved in Student Profile), the stamp no
       longer matches and the form falls back to the fresh profile prefill —
       stale form state can never overwrite newer profile data. */
  const profilePrefill = useMemo(
    () => buildPredictionDraftFromProfile(profile),
    [profile]
  );
  const profileSignature = useMemo(
    () => JSON.stringify([profileKey, profilePrefill]),
    [profileKey, profilePrefill]
  );
  const [predictionDraft, setPredictionDraft] = useState({
    signature: null,
    values: initialPredictionDraft,
  });

  const placementDraft =
    predictionDraft.signature === profileSignature
      ? predictionDraft.values
      : { ...initialPredictionDraft, ...profilePrefill };

  const setPlacementDraft = (next) => {
    const values =
      typeof next === "function" ? next(placementDraft) : next;
    setPredictionDraft({ signature: profileSignature, values });
  };

  /* Sidebar navigation: leave the profile page -> close both modals so a
     stale open state can't re-open them when the page is revisited. */
  const handleNavigate = (page, afterNavigate) => {
    if (!APP_ROUTES[page]) return false;
    if (page === currentPageRef.current) {
      afterNavigate?.();
      return true;
    }
    if (currentPageRef.current === "mocktests" && assessmentStateRef.current.active && page !== "mocktests") {
      pendingNavigationRef.current = { page, historyMode: "push", afterNavigate };
      requestAssessmentLeaveConfirmation();
      return false;
    }
    traceResume('navigation', { source: 'AppContent.handleNavigate', page: currentPage, nextPage: page,
      previous: resumeProfileOpen, next: page === 'profile' ? resumeProfileOpen : false });
    commitNavigation(page);
    afterNavigate?.();
    return true;
  };

  const handleEditProfile = () => {
    handleNavigate("profile", () => setEditProfileOpen(true));
  };

  const handleAssessmentStateChange = useCallback((state) => {
    assessmentStateRef.current = state;
  }, []);

  const handleAssessmentLeaveConfirmed = () => {
    const pending = pendingNavigationRef.current;
    pendingNavigationRef.current = null;
    const page = pending?.page ?? "dashboard";
    setShowRouteLeaveConfirmation(false);
    commitNavigation(page, pending?.historyMode ?? "push");
    pending?.afterNavigate?.();
  };

  const handleAssessmentLeaveCancelled = () => {
    const pending = pendingNavigationRef.current;
    pendingNavigationRef.current = null;
    setShowRouteLeaveConfirmation(false);
    if (pending?.historyMode === "pop") window.history.forward();
  };

  const handleLogout = async () => {
    if (logoutInFlight.current) return;
    logoutInFlight.current = true;
    setLogoutBusy(true); setLogoutError(null);
    traceResume('logout.start', { source: 'AppContent.handleLogout' });
    try {
      await logout();
      window.history.replaceState({}, "", "/login");
    }
    catch (error) { setLogoutError(error.message); }
    finally { logoutInFlight.current = false; setLogoutBusy(false); }
  };

  return (
    <div className="app">
      <a className="skip-to-content" href="#main-content" onClick={focusMainContent}>
        Skip to main content
      </a>

      {/* Top navigation */}
      <Navbar
        currentPage={currentPage}
        setCurrentPage={handleNavigate}
        onEditProfile={handleEditProfile}
        onLogout={handleLogout}
        logoutBusy={logoutBusy}
        onNewProfile={() => setNewProfileOpen(true)}
        unreadNotificationCount={unreadNotificationCount}
      />

      <div className="app-body">
        {/* Left sidebar */}
        <Sidebar
          currentPage={currentPage}
          setCurrentPage={handleNavigate}
        />

        {/* Main page content */}
        <main className="main-content" id="main-content" tabIndex={-1}>
          {logoutError && <div className="error-banner" role="alert">{logoutError}</div>}
          {!profileLoading && !profileError && ['dashboard', 'profile'].includes(currentPage) &&
            <ProfileJourneyNotice profile={rawProfile} completion={completion}
              onCreate={() => setNewProfileOpen(true)}
              onReview={(stage) => stage === 'confirm' ? handleNavigate('profile') : handleEditProfile()} />}
          {newProfileOpen && <ResumeUploadModal resumeDraft={resumeDraft}
            onDraftCreated={(result) => setPendingResumeDraft(result.draftProfile)}
            onVerified={(data) => { clearPendingResumeDraft(); setNewProfileOpen(false); refetch(data.profile.profile_id); }}
            onClose={() => setNewProfileOpen(false)} />}

          {currentPage === "dashboard" && (
            <Dashboard onNavigate={handleNavigate} />
          )}

          {(currentPage === "readiness" || currentPage === "goals" || careerReadinessVisited) && (
            <div hidden={currentPage !== "readiness" && currentPage !== "goals"}>
              <CareerReadiness
                active={currentPage === "readiness" || currentPage === "goals"}
                focusGoalManagement={currentPage === "goals" && window.location.hash === "#goal-management"}
                onNavigate={handleNavigate}
                onEditProfile={handleEditProfile}
                onCreateProfile={() => setNewProfileOpen(true)}
                notificationTarget={notificationTarget}
                onNotificationTargetHandled={() => setNotificationTarget(null)}
              />
            </div>
          )}

          {currentPage === "prediction" && (
            <Prediction
              onNavigate={handleNavigate}
              draft={placementDraft}
              onDraftChange={setPlacementDraft}
            />
          )}

          {currentPage === "experimental-v1" && <ExperimentalV1Prediction />}

          {currentPage === "salary" && (
            <SalaryPrediction />
          )}

          {currentPage === "companies" && (
            <CompanyRecommendations />
          )}

          {currentPage === "skillgap" && (
            <SkillGapAnalysis />
          )}

          {/* Keep the active assessment/deadline alive while viewing another page. */}
          <div hidden={currentPage !== "mocktests"}>
            <MockTests onNavigate={handleNavigate}
              onAssessmentStateChange={handleAssessmentStateChange}
              onAssessmentLeaveConfirmed={handleAssessmentLeaveConfirmed}
              onAssessmentLeaveCancelled={handleAssessmentLeaveCancelled} />
          </div>

          {currentPage === "profile" && (
            <StudentProfile
              key={profileId}
              editOpen={editProfileOpen}
              onRequestEdit={() => setEditProfileOpen(true)}
              onCloseEdit={() => setEditProfileOpen(false)}
              resumeOpen={resumeProfileOpen}
              onRequestResume={() => {
                traceResume('open.request', { source: 'AppContent.onRequestResume', previous: resumeProfileOpen, next: true });
                setResumeProfileOpen(true);
              }}
              onCloseResume={() => {
                traceResume('close.callback', { source: 'AppContent.onCloseResume', previous: resumeProfileOpen, next: false });
                setResumeProfileOpen(false);
              }}
            />
          )}

          {currentPage === "performance" && (
            <PerformanceAnalysis />
          )}

          {currentPage === "about" && (
            <About />
          )}

          {currentPage === "notifications" && (
            <NotificationCenter
              onUnreadCountChange={setUnreadNotificationCount}
              onOpenGoal={(notification) => {
                setNotificationTarget({ goalId: notification.goal_id, milestoneId: notification.milestone_id });
                handleNavigate('goals');
              }}
            />
          )}

          {(currentPage === "resume" || resumeBuilderVisited) && (
            <div hidden={currentPage !== "resume"}>
              <StudentResumeBuilder key={profileId} />
            </div>
          )}
        </main>
      </div>
      {showRouteLeaveConfirmation && (
        <AccessibleModal labelledBy="route-leave-test-title" describedBy="route-leave-test-description"
          onEscape={handleAssessmentLeaveCancelled} onBackdropClose={handleAssessmentLeaveCancelled}>
          <div className="modal-header"><h2 id="route-leave-test-title">Leave Test</h2></div>
          <p id="route-leave-test-description" className="confirm-text">
            Your answers are kept in this tab. The assessment deadline continues while you are away.
            Return to Mock Tests to continue.
          </p>
          <div className="modal-actions">
            <button type="button" className="dash-btn secondary" onClick={handleAssessmentLeaveCancelled} data-modal-initial-focus>Cancel</button>
            <button type="button" className="dash-btn primary" onClick={handleAssessmentLeaveConfirmed}>Leave Test</button>
          </div>
        </AccessibleModal>
      )}
    </div>
  );
}

function ProfileWorkspace() {
  const { profileId } = useStudentProfileContext();
  // All drafts/results/controllers remount when the selected identity changes.
  return <AppContent key={profileId || 'empty'} />;
}

function SessionApp() {
  const session = useAuth();
  useEffect(() => {
    if (session.status === 'authenticated') return;
    document.title = session.status === 'unavailable' ? 'PlacePro unavailable | PLACE PRO'
      : session.status === 'restoring' ? 'Restoring session | PLACE PRO' : 'Sign in | PLACE PRO';
  }, [session.status]);
  useEffect(() => {
    authSession.restore();
    const onFocus = () => authSession.restore({ background: true });
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, []);
  if (session.status === 'restoring') return <div className="session-state" role="status">Restoring your PlacePro session…</div>;
  if (session.status === 'unavailable') return <div className="session-state">
    <h1>PlacePro is unavailable</h1><p role="alert">{session.error}</p>
    <button type="button" className="dash-btn primary" onClick={() => authSession.restore()}>Retry connection</button>
  </div>;
  if (session.status !== 'authenticated') return <Login notice={session.error} />;
  return <StudentProfileProvider key={session.account.account_id + ':' + session.epoch} accountId={session.account.account_id}>
    <ProfileWorkspace />
  </StudentProfileProvider>;
}

function App() {
  useEffect(() => {
    if (!appPageFromPath(window.location.pathname)) {
      window.history.replaceState({}, "", appHrefForPage("dashboard"));
    }
  }, []);
  return <>
    {isSyntheticDemo() && <div className="synthetic-demo-notice" role="note">
      <strong>Local synthetic demonstration</strong>
      <span>Model estimates use synthetic student inputs. No real placement outcomes are shown.</span>
    </div>}
    <SessionApp />
  </>;
}

export default App;

