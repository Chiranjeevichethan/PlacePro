import { useEffect, useRef, useState } from "react";

// Local-development account setup documented in docs/dual-authentication.md.
// The synthetic launcher uses a different, operator-chosen credential.
const DEMO_CREDENTIALS =
  import.meta.env.DEV && import.meta.env.VITE_DEMO_MODE !== "synthetic"
    ? { email: "student@placepro.com" }
    : null;

function CopyIcon({ copied }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {copied ? (
        <path d="m5 12 4 4L19 6" />
      ) : (
        <>
          <rect x="9" y="9" width="13" height="13" rx="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </>
      )}
    </svg>
  );
}

function CopyCredentialButton({ label, value, disabled }) {
  const [status, setStatus] = useState("idle");
  const active = useRef(true);
  const feedbackTimeout = useRef();

  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      window.clearTimeout(feedbackTimeout.current);
    };
  }, []);

  const handleCopy = async () => {
    if (disabled || status === "copying") return;
    window.clearTimeout(feedbackTimeout.current);
    setStatus("copying");

    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(value);
      if (!active.current) return;
      setStatus("copied");
      feedbackTimeout.current = window.setTimeout(() => setStatus("idle"), 2000);
    } catch {
      if (active.current) setStatus("error");
    }
  };

  const feedback = status === "copied"
    ? `Demo ${label} copied.`
    : status === "error" ? `Couldn't copy ${label}. Try again.` : "";

  return (
    <>
      <button
        type="button"
        className={`login-demo-copy${status === "copied" ? " is-copied" : ""}${status === "error" ? " is-error" : ""}`}
        onClick={handleCopy}
        disabled={disabled || status === "copying"}
        aria-label={`Copy demo ${label}`}
        aria-busy={status === "copying"}
        title={status === "error" ? feedback : `Copy demo ${label}`}
      >
        <CopyIcon copied={status === "copied"} />
      </button>
      <span
        className={status === "error" ? "login-demo-copy-error" : "visually-hidden"}
        role="status"
        aria-live="polite"
      >
        {feedback}
      </span>
    </>
  );
}

function DemoCredentials({ disabled = false }) {
  if (!DEMO_CREDENTIALS) return null;

  return (
    <section className="login-demo" aria-label="Demo credentials">
      <h2 className="login-demo-title">Demo credentials</h2>
      <dl className="login-demo-fields">
        <div className="login-demo-field">
          <dt>Email</dt>
          <dd>
            <span className="login-demo-value">{DEMO_CREDENTIALS.email}</span>
            <CopyCredentialButton label="email" value={DEMO_CREDENTIALS.email} disabled={disabled} />
          </dd>
        </div>
        <div className="login-demo-field">
          <dt>Password</dt>
          <dd>
            <span className="login-demo-value">
              Use the password you entered when provisioning this local account.
            </span>
          </dd>
        </div>
      </dl>
    </section>
  );
}

export default DemoCredentials;
