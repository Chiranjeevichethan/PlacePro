import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  activateModalInteraction,
  containModalTab,
} from "../src/components/modalAccessibility.js";

class FakeElement {
  constructor(documentRef, attributes = {}) {
    this.documentRef = documentRef;
    this.attributes = new Map(Object.entries(attributes));
    this.children = [];
    this.parentElement = null;
    this.hidden = false;
    this.disabled = false;
    this.isConnected = true;
    this.style = {};
    this.focusCount = 0;
  }

  append(child) {
    child.parentElement = this;
    this.children.push(child);
    return child;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  getClientRects() {
    return this.hidden ? [] : [{}];
  }

  querySelectorAll() {
    return this.children;
  }

  querySelector(selector) {
    if (selector === "main") {
      return this.children.find((child) => child.tagName === "MAIN") ?? null;
    }
    if (selector === "[data-modal-initial-focus]") {
      return this.children.find((child) => child.hasAttribute("data-modal-initial-focus")) ?? null;
    }
    return null;
  }

  contains(element) {
    return this.children.some((child) => child === element || child.contains(element));
  }

  focus() {
    this.focusCount += 1;
    this.documentRef.activeElement = this;
  }
}

class FakeDocument {
  constructor() {
    this.activeElement = null;
    this.listeners = new Map();
    this.body = new FakeElement(this);
  }

  addEventListener(type, callback) {
    const callbacks = this.listeners.get(type) ?? new Set();
    callbacks.add(callback);
    this.listeners.set(type, callbacks);
  }

  removeEventListener(type, callback) {
    this.listeners.get(type)?.delete(callback);
  }

  dispatch(type, event) {
    for (const callback of this.listeners.get(type) ?? []) callback(event);
  }
}

function setupModal({ focusableCount = 2, initialFocus = false } = {}) {
  const documentRef = new FakeDocument();
  const opener = new FakeElement(documentRef);
  documentRef.activeElement = opener;
  const root = new FakeElement(documentRef);
  const main = root.append(new FakeElement(documentRef));
  main.tagName = "MAIN";
  const body = documentRef.body;
  body.style.overflow = "auto";
  const dialog = new FakeElement(documentRef);
  const focusable = Array.from({ length: focusableCount }, (_, index) =>
    dialog.append(new FakeElement(documentRef, initialFocus && index === 0
      ? { "data-modal-initial-focus": "" }
      : {}))
  );
  return { documentRef, opener, root, body, dialog, focusable, main };
}

function tabEvent({ shiftKey = false } = {}) {
  return {
    key: "Tab",
    shiftKey,
    defaultPrevented: false,
    preventDefault() { this.defaultPrevented = true; },
    stopPropagation() {},
  };
}

test("modal focuses its requested control and makes the app background inert", () => {
  const modal = setupModal({ initialFocus: true });
  activateModalInteraction({
    ...modal,
    onEscape() {},
    isCloseBlocked: () => false,
  });

  assert.equal(modal.documentRef.activeElement, modal.focusable[0]);
  assert.equal(modal.root.hasAttribute("inert"), true);
  assert.equal(modal.body.style.overflow, "hidden");
});

test("Tab and Shift+Tab wrap at the modal boundaries", () => {
  const modal = setupModal();
  const forward = tabEvent();
  containModalTab(forward, modal.dialog, modal.focusable.at(-1));
  assert.equal(forward.defaultPrevented, true);
  assert.equal(modal.documentRef.activeElement, modal.focusable[0]);

  const backward = tabEvent({ shiftKey: true });
  containModalTab(backward, modal.dialog, modal.focusable[0]);
  assert.equal(backward.defaultPrevented, true);
  assert.equal(modal.documentRef.activeElement, modal.focusable.at(-1));
});

test("a modal without focusable controls keeps Tab focus on the dialog", () => {
  const modal = setupModal({ focusableCount: 0 });
  const event = tabEvent();
  containModalTab(event, modal.dialog, modal.opener);

  assert.equal(event.defaultPrevented, true);
  assert.equal(modal.documentRef.activeElement, modal.dialog);
});

test("disabled and hidden controls are skipped when trapping focus", () => {
  const modal = setupModal();
  modal.focusable[0].disabled = true;
  modal.focusable[1].hidden = true;
  const event = tabEvent();
  containModalTab(event, modal.dialog, modal.opener);

  assert.equal(event.defaultPrevented, true);
  assert.equal(modal.documentRef.activeElement, modal.dialog);
});

test("Escape invokes the close callback unless the modal is busy", () => {
  const modal = setupModal();
  let blocked = false;
  let closeCount = 0;
  activateModalInteraction({
    ...modal,
    onEscape() { closeCount += 1; },
    isCloseBlocked: () => blocked,
  });

  const event = {
    key: "Escape",
    defaultPrevented: false,
    propagationStopped: false,
    preventDefault() { this.defaultPrevented = true; },
    stopPropagation() { this.propagationStopped = true; },
  };
  modal.documentRef.dispatch("keydown", event);
  assert.equal(closeCount, 1);
  assert.equal(event.defaultPrevented, true);
  assert.equal(event.propagationStopped, true);

  blocked = true;
  modal.documentRef.dispatch("keydown", event);
  assert.equal(closeCount, 1);
});

test("focus leaving the dialog is redirected back inside", () => {
  const modal = setupModal();
  activateModalInteraction({
    ...modal,
    onEscape() {},
    isCloseBlocked: () => false,
  });
  modal.documentRef.activeElement = modal.opener;
  modal.documentRef.dispatch("focusin", { target: modal.opener });

  assert.equal(modal.documentRef.activeElement, modal.dialog);
});

test("closing restores opener focus and prior background state", () => {
  const modal = setupModal();
  modal.root.setAttribute("inert", "");
  const cleanup = activateModalInteraction({
    ...modal,
    onEscape() {},
    isCloseBlocked: () => false,
  });
  cleanup();

  assert.equal(modal.documentRef.activeElement, modal.opener);
  assert.equal(modal.root.hasAttribute("inert"), true);
  assert.equal(modal.body.style.overflow, "auto");
});

test("if the opener is removed, focus falls back to main content", () => {
  const modal = setupModal();
  const cleanup = activateModalInteraction({
    ...modal,
    onEscape() {},
    isCloseBlocked: () => false,
  });
  modal.opener.isConnected = false;
  cleanup();

  assert.equal(modal.documentRef.activeElement, modal.main);
  assert.equal(modal.main.hasAttribute("tabindex"), false);
});

test("all current modal workflows use the shared accessible modal", () => {
  const edit = readFileSync(new URL("../src/components/EditProfileModal.jsx", import.meta.url), "utf8");
  const resume = readFileSync(new URL("../src/components/ResumeUploadModal.jsx", import.meta.url), "utf8");
  const tests = readFileSync(new URL("../src/pages/MockTests.jsx", import.meta.url), "utf8");

  assert.match(edit, /<AccessibleModal[\s\S]*?labelledBy="edit-profile-title"/);
  assert.match(edit, /describedBy="edit-profile-description"/);
  assert.match(resume, /<AccessibleModal[\s\S]*?labelledBy="resume-modal-title"/);
  assert.match(resume, /describedBy=\{step === "upload"[\s\S]*?resume-modal-description-review/);
  assert.equal((tests.match(/<AccessibleModal/g) ?? []).length, 2);
  assert.match(tests, /labelledBy="submit-confirm-title"[\s\S]*?describedBy="submit-confirm-description"/);
  assert.match(tests, /labelledBy="exit-confirm-title"[\s\S]*?describedBy="exit-confirm-description"/);
  assert.doesNotMatch(edit + resume + tests, /role="dialog"/);
});
