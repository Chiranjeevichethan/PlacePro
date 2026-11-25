import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const css = await readFile(new URL("../src/App.css", import.meta.url), "utf8");
const app = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const mockTests = await readFile(new URL("../src/pages/MockTests.jsx", import.meta.url), "utf8");

test("common form controls and action buttons share the same geometry tokens", () => {
  assert.match(css, /--control-height:\s*44px/);
  assert.match(css, /--control-radius:\s*10px/);
  assert.match(css, /\.dash-btn\s*\{[^}]*min-height:\s*var\(--control-height\)[^}]*border-radius:\s*var\(--control-radius\)/);
  assert.match(css, /\.form-group input,\s*\.form-group select\s*\{[^}]*border-radius:\s*var\(--control-radius\)/);
  assert.match(css, /\.form-group input,\s*\.form-group select\s*\{[^}]*min-height:\s*44px/);
});

test("company and resource cards use the shared surface and hover elevation tokens", () => {
  assert.match(css, /--card-surface:\s*linear-gradient/);
  assert.match(css, /--card-border:\s*rgba\(226, 232, 240, 0\.95\)/);
  assert.match(css, /--shadow-card-hover:\s*0 2px 4px/);
  assert.match(css, /\.company-card,\s*\.resource-card\s*\{\s*background:\s*var\(--card-surface\);\s*border:\s*1px solid var\(--card-border\);\s*box-shadow:\s*var\(--shadow-card\)/);
  assert.match(css, /\.company-card:hover,\s*\.resource-card:hover\s*\{[^}]*transform:\s*translateY\(-3px\)[^}]*box-shadow:\s*var\(--shadow-card-hover\)/);
  assert.match(css, /\.company-card\.incomplete\s*\{\s*border-color:\s*#f2d58d/);
});

test("visual polish retains the established focus, disabled, skip-link, and Mock Tests safeguards", () => {
  assert.match(css, /:focus-visible\s*\{[^}]*outline:/);
  assert.match(css, /\.dashboard \.dash-btn:disabled\s*\{/);
  assert.match(app, /className="skip-to-content" href="#main-content"/);
  assert.match(app, /<div hidden=\{currentPage !== "mocktests"\}>\s*<MockTests onNavigate=\{handleNavigate\}[\s\S]*?onAssessmentStateChange=\{handleAssessmentStateChange\}[\s\S]*?\/>/);
  assert.match(mockTests, /\{showExitConfirm && \([\s\S]*?labelledBy="exit-confirm-title"/);
});
