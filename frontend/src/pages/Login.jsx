import { useState } from "react";
import Logo from "../components/Logo";
import DemoCredentials from "../components/DemoCredentials";
import { login, register, startGoogleLogin, consumeAuthReturn } from "../services/auth";
import { readLoginEmail, rememberLoginEmail } from "../services/loginEmailDraft.js";

const FORGOT_MESSAGE =
  "Password recovery is unavailable until an approved email workflow is connected.";

function UserIcon() {
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
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function LockIcon() {
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
      <rect x="3" y="11" width="18" height="11" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function EyeIcon() {
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
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
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
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

function ShieldIcon() {
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
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09c.95-2.85 3.6-4.96 6.73-4.96z"
      />
    </svg>
  );
}

function LoginBackground() {
  return (
    <>
      <svg
        className="login-bg-art login-bg-art-top"
        viewBox="0 0 400 400"
        role="presentation"
        aria-hidden="true"
      >
        <path className="bg-curve" d="M-20 300 C 120 180, 260 220, 420 120" />
        <path className="bg-curve" d="M-20 380 C 160 260, 300 300, 420 200" />
        <circle className="bg-node" cx="140" cy="205" r="4" />
        <circle className="bg-node" cx="300" cy="145" r="3" />
        <circle className="bg-dot" cx="90" cy="150" r="2" />
        <circle className="bg-dot" cx="210" cy="95" r="2" />
        <circle className="bg-dot" cx="350" cy="70" r="2" />
      </svg>

      <svg
        className="login-bg-art login-bg-art-bottom"
        viewBox="0 0 400 400"
        role="presentation"
        aria-hidden="true"
      >
        <path className="bg-curve" d="M-20 300 C 120 180, 260 220, 420 120" />
        <path className="bg-curve" d="M-20 380 C 160 260, 300 300, 420 200" />
        <circle className="bg-node" cx="150" cy="180" r="4" />
        <circle className="bg-node" cx="310" cy="120" r="3" />
        <circle className="bg-dot" cx="80" cy="130" r="2" />
        <circle className="bg-dot" cx="230" cy="75" r="2" />
        <circle className="bg-dot" cx="360" cy="50" r="2" />
      </svg>
    </>
  );
}

function Login({ onLogin, notice: initialNotice, initialError = "" }) {
  const [returned] = useState(() => consumeAuthReturn());
  const [username, setUsername] = useState(readLoginEmail);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState(initialError || returned?.error || "");
  const [note, setNote] = useState(returned?.error ? "" : initialNotice || "");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const busy = loading || googleLoading;

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (busy) return;

    setError("");
    setNote("");
    setLoading(true);

    try {
      if (registering) {
        if (password !== confirmation) throw new Error('The passwords do not match.');
        setNote(await register(username, password));
        setPassword(''); setConfirmation('');
        return;
      }
      const ok = await login(username, password);

      if (ok) {
        setUsername(''); setPassword(''); onLogin?.();
      } else {
        setError("Invalid email or password.");
      }
    } catch (error) {
      setError(error.message || 'Unable to sign in. Please retry.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    if (busy) return;
    setError("");
    setNote("");
    setGoogleLoading(true);
    try {
      await startGoogleLogin();
    } catch (error) {
      setError(error.message || 'Google sign-in is unavailable. Please retry.');
      setGoogleLoading(false);
    }
  };

  return (
    <div className="login-page">
      <LoginBackground />

      <div className="login-card">
        <div className="login-logo">
          <Logo variant="stacked" size={72} />
        </div>

        <h1 className="login-title">{registering ? 'Create your account' : 'Welcome Back'}</h1>

        <p className="login-subtitle">
          {registering ? 'Student registration is pending an approved email activation workflow.' : 'Sign in to continue to your placement dashboard.'}
        </p>

        {(note || initialNotice) && !error && <div className="login-note" role="status">{note || initialNotice}</div>}
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="login-username">Student email</label>

            <div className="input-wrap">
              <span className="input-icon" aria-hidden="true">
                <UserIcon />
              </span>

              <input
                id="login-username"
                type="email"
                required
                maxLength={254}
                disabled={busy}
                value={username}
                onChange={(event) => {
                  setUsername(event.target.value);
                  rememberLoginEmail(event.target.value);
                }}
                placeholder="student@placepro.com"
                autoComplete="username"
                autoFocus
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="login-password">Password</label>

            <div className="input-wrap">
              <span className="input-icon" aria-hidden="true">
                <LockIcon />
              </span>

              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                autoComplete={registering ? 'new-password' : 'current-password'}
                required
                minLength={registering ? 12 : undefined}
                maxLength={128}
                disabled={busy}
                className="has-toggle"
              />

              <button
                type="button"
                className="input-toggle"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
              >
                {showPassword ? <EyeOffIcon /> : <EyeIcon />}
              </button>
            </div>
          </div>

          {registering && <div className="form-group">
            <label htmlFor="register-confirmation">Confirm password</label>
            <input id="register-confirmation" type="password" value={confirmation} required disabled={busy}
              autoComplete="new-password" onChange={(event) => setConfirmation(event.target.value)} />
            <small>Use 12–128 characters. Passwords are never saved in browser storage.</small>
          </div>}
          <div className="login-options">
            <button
              type="button"
              className="login-forgot"
              onClick={() => setNote(FORGOT_MESSAGE)}
            >
              Forgot Password?
            </button>
          </div>

          {error && <div className="login-error" role="alert">{error}</div>}

          <button type="submit" className="login-button" disabled={busy}>
            {loading ? (registering ? 'Submitting…' : 'Signing you in...') : (registering ? 'Request registration' : 'LOGIN')}
          </button>
        </form>

        {!registering && <DemoCredentials disabled={busy} />}

        <div className="login-divider">
          <span>OR</span>
        </div>

        <div className="social-login">
          <button
            type="button"
            className="social-login-btn"
            onClick={handleGoogle}
            disabled={busy}
          >
            <GoogleIcon />
            <span>{googleLoading ? 'Redirecting to Google…' : 'Continue with Google'}</span>
          </button>
        </div>

        <p className="login-create">
          New student?{" "}
          <button
            type="button"
            className="login-link-inline"
            disabled={busy}
            onClick={() => { setRegistering((value) => !value); setError(''); setNote(''); setPassword(''); setConfirmation(''); }}
          >
            {registering ? 'Back to login' : 'Student registration'}
          </button>
        </p>

        <div className="login-info">
          <span className="login-info-icon" aria-hidden="true">
            <ShieldIcon />
          </span>

          <span>
            Email and Google sign-in use the same secure server session. Only verified accounts can sign in.
          </span>
        </div>
      </div>
    </div>
  );
}

export default Login;
