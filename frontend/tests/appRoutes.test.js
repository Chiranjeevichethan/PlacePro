import assert from "node:assert/strict";
import test from "node:test";
import {
  APP_ROUTES, appHrefForPage, appPageFromPath, appPathForPage, appTitleForPage, handleAppLinkClick,
} from "../src/services/appRoutes.js";

test("every main page has a stable unique URL and document title", () => {
  const routes = Object.entries(APP_ROUTES);
  assert.ok(routes.length >= 12);
  assert.equal(new Set(routes.map(([, route]) => route.path)).size, routes.length);
  for (const [page, route] of routes) {
    assert.equal(appPathForPage(page), route.path);
    assert.equal(appPageFromPath(route.path), page);
    assert.ok(route.title.trim());
    assert.equal(appTitleForPage(page), route.title);
  }
  assert.equal(appHrefForPage("resume"), "/resume-builder");
  assert.equal(appHrefForPage("goals"), "/goals#goal-management");
});

test("root and login resolve to Dashboard while unknown paths are detectable", () => {
  assert.equal(appPageFromPath("/"), "dashboard");
  assert.equal(appPageFromPath("/login"), "dashboard");
  assert.equal(appPageFromPath("/resume-builder/"), "resume");
  assert.equal(appPageFromPath("/not-a-placepro-route"), null);
});

test("plain primary clicks use client navigation while modified clicks keep native link behavior", () => {
  const calls = [];
  const createEvent = (overrides = {}) => ({
    defaultPrevented: false, button: 0, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false,
    preventDefault() { this.defaultPrevented = true; }, ...overrides,
  });
  const plain = createEvent();
  handleAppLinkClick(plain, "resume", (page) => calls.push(page));
  assert.equal(plain.defaultPrevented, true);
  assert.deepEqual(calls, ["resume"]);

  const modified = createEvent({ ctrlKey: true });
  handleAppLinkClick(modified, "goals", (page) => calls.push(page));
  assert.equal(modified.defaultPrevented, false);
  assert.deepEqual(calls, ["resume"]);
});
