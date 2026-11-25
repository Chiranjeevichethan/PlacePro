import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { focusMainContent } from "../src/services/skipToContent.js";

const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const appCss = await readFile(new URL("../src/App.css", import.meta.url), "utf8");
const indexCss = await readFile(new URL("../src/index.css", import.meta.url), "utf8");

test("skip link is the first app control and targets the focusable main landmark", () => {
  const linkIndex = appSource.indexOf('className="skip-to-content"');
  const navbarIndex = appSource.indexOf("<Navbar");

  assert.notEqual(linkIndex, -1);
  assert.ok(linkIndex < navbarIndex);
  assert.match(appSource, /<a className="skip-to-content" href="#main-content" onClick=\{focusMainContent\}>\s*Skip to main content\s*<\/a>/);
  assert.match(appSource, /<main className="main-content" id="main-content" tabIndex=\{-1\}>/);
});

test("skip-link activation moves focus to the main landmark", () => {
  let focused = false;
  const main = { focus: () => { focused = true; } };
  const event = {
    currentTarget: {
      ownerDocument: {
        getElementById: (id) => id === "main-content" ? main : null,
      },
    },
  };

  focusMainContent(event);

  assert.equal(focused, true);
});

test("skip-link activation safely handles a missing main target", () => {
  assert.doesNotThrow(() => focusMainContent({
    currentTarget: { ownerDocument: { getElementById: () => null } },
  }));
});

test("global focus-visible styling covers native and custom controls", () => {
  assert.match(appCss, /body :is\([\s\S]*?a\[href\][\s\S]*?button[\s\S]*?input:not\(\[type="hidden"\]\)[\s\S]*?select[\s\S]*?textarea[\s\S]*?summary[\s\S]*?\[role="button"\][\s\S]*?\):focus-visible\s*\{/);
  assert.match(appCss, /outline:\s*2px solid var\(--focus-ring-color\)/);
  assert.match(appCss, /outline-offset:\s*3px/);
  assert.match(indexCss, /--focus-ring-color:\s*#1d4ed8/);
  assert.match(indexCss, /--focus-ring-contrast:\s*#ffffff/);
});
