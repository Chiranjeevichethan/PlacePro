import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const app = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const sidebar = await readFile(new URL("../src/components/Sidebar.jsx", import.meta.url), "utf8");
const navbar = await readFile(new URL("../src/components/Navbar.jsx", import.meta.url), "utf8");
const dropdown = await readFile(new URL("../src/components/ProfileDropdown.jsx", import.meta.url), "utf8");
const search = await readFile(new URL("../src/components/SearchBar.jsx", import.meta.url), "utf8");
const css = await readFile(new URL("../src/App.css", import.meta.url), "utf8");
const mockTests = await readFile(new URL("../src/pages/MockTests.jsx", import.meta.url), "utf8");
const goalManagement = await readFile(new URL("../src/components/GoalManagement.jsx", import.meta.url), "utf8");

test("primary navigation and page discovery use meaningful links with current-page state", () => {
  assert.match(sidebar, /<nav className="sidebar-menu" aria-label="Primary navigation">/);
  assert.match(sidebar, /<a\s+href=\{appHrefForPage\(item\.page\)\}[\s\S]*?aria-current=\{currentPage === item\.page \? "page" : undefined\}[\s\S]*?handleAppLinkClick/);
  assert.match(sidebar, /page: "goals", label: "Goals & Milestones"/);
  assert.match(navbar, /<a\s+href=\{appHrefForPage\("notifications"\)\}/);
  assert.match(search, /<a\s+href=\{appHrefForPage\(item\.page\)\}/);
  assert.match(dropdown, /href=\{appHrefForPage\("profile"\)\}/);
  assert.match(css, /\.sidebar-menu :is\(a, button\):focus-visible|\.sidebar-menu :is\(a, button\)\s*\{/);
});

test("URL state initializes the app and handles navigation, Back/Forward, unknown routes, title, and focus", () => {
  assert.match(app, /useState\(\(\) => appPageFromPath\(window\.location\.pathname\) \|\| "dashboard"\)/);
  assert.match(app, /window\.history\.pushState\(\{ placeProPage: page \}, "", path\)/);
  assert.match(app, /window\.addEventListener\("popstate", onPopState\)/);
  assert.match(app, /document\.title = `\$\{appTitleForPage\(currentPage\)\} \| PLACE PRO`/);
  assert.match(app, /getElementById\("main-content"\)\?\.focus/);
  assert.match(app, /if \(!appPageFromPath\(window\.location\.pathname\)\)/);
  assert.match(app, /handleNavigate\('goals'\)/);
});

test("Goals and Milestones has a direct anchored route that focuses its heading", () => {
  assert.match(app, /currentPage === "goals"/);
  assert.match(app, /window\.location\.hash !== "#goal-management"/);
  assert.match(app, /getElementById\("goal-management-title"\)/);
  assert.match(goalManagement, /id="goal-management"[\s\S]*?id="goal-management-title" tabIndex=\{-1\}/);
  assert.match(goalManagement, /window\.location\.hash !== '#goal-management'[\s\S]*?heading\.focus/);
});

test("the authenticated Resume Builder draft stays mounted in memory across app routes", () => {
  assert.match(app, /currentPage === "resume" \|\| resumeBuilderVisited/);
  assert.match(app, /<div hidden=\{currentPage !== "resume"\}>\s*<StudentResumeBuilder key=\{profileId\} \/>/);
});

test("Mock Tests stays mounted while its timer and assessment state survive route changes", () => {
  assert.match(app, /<div hidden=\{currentPage !== "mocktests"\}>\s*<MockTests[\s\S]*?onAssessmentStateChange=\{handleAssessmentStateChange\}/);
  assert.match(app, /return <AppContent key=\{profileId \|\| 'empty'\} \/>/);
  assert.match(app, /<StudentProfileProvider key=\{session\.account\.account_id \+ ':' \+ session\.epoch\}/);
  assert.match(mockTests, /onAssessmentStateChange\?\.\(\{[\s\S]*?active: state\.phase === "loading" \|\| state\.phase === "running"/);
  assert.match(mockTests, /window\.addEventListener\("placepro:request-assessment-leave", requestLeave\)/);
  assert.match(mockTests, /if \(showSubmitConfirm\) queuedExitConfirm\.current = true;\s*else setShowExitConfirm\(true\)/);
  assert.match(mockTests, /onCancelExit\?\.\(\)/);
  assert.match(mockTests, /onExit=\{onAssessmentLeaveConfirmed\}/);
});

test("navigation attempts during an active assessment reuse its existing leave confirmation", () => {
  assert.match(app, /currentPageRef\.current === "mocktests" && assessmentStateRef\.current\.active/);
  assert.match(app, /pendingNavigationRef\.current = \{ page, historyMode: "pop" \}/);
  assert.match(app, /if \(pending\?\.historyMode === "pop"\) window\.history\.forward\(\)/);
  assert.match(mockTests, /Your answers are kept in this tab\. The assessment deadline continues while you are away\./);
  assert.match(mockTests, /onAssessmentLeaveConfirmed/);
});
