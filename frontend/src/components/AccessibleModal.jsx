import { useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { activateModalInteraction } from "./modalAccessibility";

function AccessibleModal({
  labelledBy,
  describedBy,
  onEscape,
  closeBlocked = false,
  onBackdropClose,
  className = "modal-card",
  children,
}) {
  const dialogRef = useRef(null);
  const currentOptions = useRef({ onEscape, closeBlocked, onBackdropClose });

  useLayoutEffect(() => {
    currentOptions.current = { onEscape, closeBlocked, onBackdropClose };
  }, [onEscape, closeBlocked, onBackdropClose]);

  useLayoutEffect(() =>
    activateModalInteraction({
      dialog: dialogRef.current,
      root: document.getElementById("root"),
      body: document.body,
      documentRef: document,
      onEscape: (event) => currentOptions.current.onEscape?.(event),
      isCloseBlocked: () => currentOptions.current.closeBlocked,
    }), []);

  return createPortal(
    <div
      className="modal-overlay"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget && !currentOptions.current.closeBlocked) {
          currentOptions.current.onBackdropClose?.(event);
        }
      }}
    >
      <div
        ref={dialogRef}
        className={className}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>,
    document.body
  );
}

export default AccessibleModal;
