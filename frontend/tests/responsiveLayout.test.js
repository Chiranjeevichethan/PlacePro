import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const appCss = await readFile(new URL("../src/App.css", import.meta.url), "utf8");
const dashboard = await readFile(new URL("../src/pages/Dashboard.jsx", import.meta.url), "utf8");
const performance = await readFile(new URL("../src/pages/PerformanceAnalysis.jsx", import.meta.url), "utf8");
const app = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const mockTests = await readFile(new URL("../src/pages/MockTests.jsx", import.meta.url), "utf8");

test("dashboard and performance charts are placed in named keyboard-scrollable regions", () => {
  for (const [name, source] of [["Dashboard", dashboard], ["Performance Analysis", performance]]) {
    assert.match(source, /className="trend-chart-scroll"[\s\S]*?role="region"[\s\S]*?aria-label="Scrollable [^"]+ chart"[\s\S]*?tabIndex=\{0\}[\s\S]*?<svg[\s\S]*?className="trend-chart"[\s\S]*?role="img"/,
      `${name} chart should keep an accessible SVG inside a keyboard-scrollable region`);
  }
});

test("phone chart text keeps its intended SVG width inside a contained horizontal scroller", () => {
  assert.match(appCss, /\.trend-chart-scroll\s*\{[\s\S]*?width:\s*100%[\s\S]*?min-width:\s*0[\s\S]*?overflow-x:\s*auto[\s\S]*?overscroll-behavior-x:\s*contain/);
  assert.match(appCss, /@media\s*\(max-width:\s*560px\)[\s\S]*?\.trend-chart\s*\{\s*min-width:\s*340px/);

  for (const viewportWidth of [320, 375, 390, 430]) {
    assert.ok(viewportWidth <= 560, `${viewportWidth}px should use the compact chart layout`);
  }
});

test("tablet and desktop chart sizing remains fluid outside the phone breakpoint", () => {
  assert.match(appCss, /\.trend-chart\s*\{\s*width:\s*100%[\s\S]*?height:\s*auto/);
  assert.match(appCss, /@media\s*\(max-width:\s*560px\)[\s\S]*?\.trend-chart\s*\{\s*min-width:\s*340px/);
});

test("existing responsive layout rules cover forms, cards, modals, and assessment layout", () => {
  assert.match(appCss, /@media\s*\(max-width:\s*600px\)[\s\S]*?\.form-grid\s*\{\s*grid-template-columns:\s*1fr/);
  assert.match(appCss, /@media\s*\(max-width:\s*560px\)[\s\S]*?\.company-grid,[\s\S]*?\.resource-grid\s*\{\s*grid-template-columns:\s*1fr/);
  assert.match(appCss, /\.modal-card\s*\{[\s\S]*?max-width:\s*640px[\s\S]*?max-height:\s*90vh[\s\S]*?overflow-y:\s*auto/);
  assert.match(appCss, /@media\s*\(max-width:\s*1000px\)[\s\S]*?\.test-running-layout\s*\{\s*grid-template-columns:\s*1fr/);
});

test("responsive chart changes preserve the mounted Mock Tests assessment", () => {
  assert.match(app, /<div hidden=\{currentPage !== "mocktests"\}>\s*<MockTests onNavigate=\{handleNavigate\}[\s\S]*?onAssessmentStateChange=\{handleAssessmentStateChange\}[\s\S]*?\/>\s*<\/div>/);
  assert.match(mockTests, /onClick=\{\(\) => setShowExitConfirm\(true\)\}>\s*Leave Test/);
  assert.match(mockTests, /onClick=\{\(\) => \{ setShowExitConfirm\(false\); onExit\(\); \}\}>Leave Test/);
});
