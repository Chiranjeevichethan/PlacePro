export const APP_ROUTES = Object.freeze({
  dashboard: { path: "/dashboard", title: "Dashboard" },
  readiness: { path: "/career-readiness", title: "Career Readiness" },
  goals: { path: "/goals", title: "Goals and Milestones" },
  notifications: { path: "/notifications", title: "Notifications" },
  resume: { path: "/resume-builder", title: "Resume Builder" },
  prediction: { path: "/placement-prediction", title: "Placement Prediction" },
  "experimental-v1": { path: "/experimental-v1-prediction", title: "Experimental V1 Prediction" },
  salary: { path: "/salary-prediction", title: "Salary Prediction" },
  companies: { path: "/company-recommendations", title: "Company Recommendations" },
  skillgap: { path: "/skill-gap-analysis", title: "Skill Gap Analysis" },
  mocktests: { path: "/mock-tests", title: "Mock Tests" },
  profile: { path: "/student-profile", title: "Student Profile" },
  performance: { path: "/performance-analysis", title: "Performance Analysis" },
  about: { path: "/about", title: "About" },
});

const PAGE_BY_PATH = new Map([
  ["/", "dashboard"],
  ["/login", "dashboard"],
  ...Object.entries(APP_ROUTES).map(([page, route]) => [route.path, page]),
]);

export function appPageFromPath(pathname) {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  return PAGE_BY_PATH.get(normalized) ?? null;
}

export function appPathForPage(page) {
  return APP_ROUTES[page]?.path ?? APP_ROUTES.dashboard.path;
}

export function appHrefForPage(page) {
  return page === "goals" ? `${appPathForPage(page)}#goal-management` : appPathForPage(page);
}

export function appTitleForPage(page) {
  return APP_ROUTES[page]?.title ?? APP_ROUTES.dashboard.title;
}

export function handleAppLinkClick(event, page, onNavigate) {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey ||
      event.shiftKey || event.altKey) return;
  event.preventDefault();
  onNavigate(page);
}

