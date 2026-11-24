const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not(:disabled)",
  "input:not(:disabled):not([type=\"hidden\"])",
  "select:not(:disabled)",
  "textarea:not(:disabled)",
  "[tabindex]:not([tabindex=\"-1\"])",
].join(",");

export function getModalFocusableElements(dialog) {
  return Array.from(dialog.querySelectorAll(FOCUSABLE_SELECTOR)).filter(
    (element) =>
      !element.disabled &&
      !element.hidden &&
      element.getAttribute("aria-hidden") !== "true" &&
      !element.closest?.('[hidden], [inert], [aria-hidden="true"]') &&
      (typeof element.checkVisibility === "function"
        ? element.checkVisibility()
        : element.getClientRects().length > 0)
  );
}

export function containModalTab(event, dialog, activeElement) {
  const focusable = getModalFocusableElements(dialog);

  if (focusable.length === 0) {
    event.preventDefault();
    dialog.focus({ preventScroll: true });
    return;
  }

  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const activeIsInside = dialog.contains(activeElement);

  if (event.shiftKey && (!activeIsInside || activeElement === first || activeElement === dialog)) {
    event.preventDefault();
    last.focus({ preventScroll: true });
  } else if (!event.shiftKey && (!activeIsInside || activeElement === last || activeElement === dialog)) {
    event.preventDefault();
    first.focus({ preventScroll: true });
  }
}

function focusSafely(element) {
  if (typeof element?.focus === "function") {
    element.focus({ preventScroll: true });
  }
}

export function activateModalInteraction({
  dialog,
  root,
  body,
  documentRef,
  onEscape,
  isCloseBlocked,
}) {
  const doc = documentRef;
  const opener = doc.activeElement;
  const rootWasInert = root?.hasAttribute("inert") ?? false;
  const previousBodyOverflow = body?.style.overflow ?? "";

  root?.setAttribute("inert", "");
  if (body) body.style.overflow = "hidden";

  const focusInitial = () => {
    const requested = dialog.querySelector("[data-modal-initial-focus]");
    const focusable = getModalFocusableElements(dialog);
    focusSafely(requested && focusable.includes(requested) ? requested : dialog);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Escape") {
      if (!isCloseBlocked()) {
        event.preventDefault();
        event.stopPropagation();
        onEscape(event);
      }
      return;
    }

    if (event.key === "Tab") {
      containModalTab(event, dialog, doc.activeElement);
    }
  };

  const handleFocusIn = (event) => {
    if (!dialog.contains(event.target)) focusInitial();
  };

  doc.addEventListener("keydown", handleKeyDown, true);
  doc.addEventListener("focusin", handleFocusIn, true);
  focusInitial();

  return () => {
    doc.removeEventListener("keydown", handleKeyDown, true);
    doc.removeEventListener("focusin", handleFocusIn, true);

    if (root && !rootWasInert) root.removeAttribute("inert");
    if (root && rootWasInert) root.setAttribute("inert", "");
    if (body) body.style.overflow = previousBodyOverflow;

    if (opener?.isConnected) {
      focusSafely(opener);
    } else {
      const fallback = root?.querySelector("main") ?? body;
      if (fallback) {
        const hadTabIndex = fallback.hasAttribute?.("tabindex") ?? false;
        if (!hadTabIndex) fallback.setAttribute?.("tabindex", "-1");
        focusSafely(fallback);
        if (!hadTabIndex) fallback.removeAttribute?.("tabindex");
      }
    }
  };
}
