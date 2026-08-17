import { useState } from "react";
import Logo from "../components/Logo";
import { login, socialLogin } from "../services/auth";

const FORGOT_MESSAGE =
  "Password recovery will be available when backend authentication is connected.";

const CREATE_MESSAGE =
  "Account registration will be available when backend authentication is connected.";

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

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.27-.01-1.17-.02-2.12-3.2.7-3.87-1.36-3.87-1.36-.52-1.33-1.28-1.68-1.28-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.03 1.76 2.69 1.25 3.35.96.1-.75.4-1.25.72-1.54-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.18-3.09-.12-.29-.51-1.46.11-3.05 0 0 .96-.31 3.15 1.18a10.9 10.9 0 0 1 5.74 0c2.19-1.49 3.15-1.18 3.15-1.18.62 1.59.23 2.76.11 3.05.73.81 1.18 1.83 1.18 3.09 0 4.41-2.69 5.38-5.25 5.67.41.35.77 1.05.77 2.12 0 1.53-.01 2.76-.01 3.14 0 .31.21.67.8.56A10.52 10.52 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5z" />
    </svg>
  );
}

function LinkedInIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.36V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.55C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.72C24 .77 23.2 0 22.22 0z" />
    </svg>
  );
}

const SOCIAL_PROVIDERS = [
  { name: "Google", Icon: GoogleIcon },
  { name: "GitHub", Icon: GitHubIcon },
  { name: "LinkedIn", Icon: LinkedInIcon },
];

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

function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (loading) return;

    setError("");
    setNote("");
    setLoading(true);

    try {
      const ok = await login(username, password, remember);

      if (ok) {
        onLogin();
      } else {
        setError("Invalid username or password.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSocial = async (name) => {
    const message = await socialLogin(name);
    setNote(message);
  };

  return (
    <div className="login-page">
      <LoginBackground />

      <div className="login-card">
        <div className="login-logo">
          <Logo variant="stacked" size={72} />
        </div>

        <h1 className="login-title">Welcome Back</h1>

        <p className="login-subtitle">
          Sign in to continue to your placement dashboard.
        </p>

        <form className="login-form" onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label htmlFor="login-username">Email / Username</label>

            <div className="input-wrap">
              <span className="input-icon" aria-hidden="true">
                <UserIcon />
              </span>

              <input
                id="login-username"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
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
                autoComplete="current-password"
                className="has-toggle"
              />

              <button
                type="button"
                className="input-toggle"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOffIcon /> : <EyeIcon />}
              </button>
            </div>
          </div>

          <div className="login-options">
            <label className="login-remember">
              <input
                type="checkbox"
                checked={remember}
                onChange={(event) => setRemember(event.target.checked)}
              />
              <span>Remember me</span>
            </label>

            <button
              type="button"
              className="login-forgot"
              onClick={() => setNote(FORGOT_MESSAGE)}
            >
              Forgot Password?
            </button>
          </div>

          {error && <div className="login-error" role="alert">{error}</div>}

          <button type="submit" className="login-button" disabled={loading}>
            {loading ? "Signing you in..." : "LOGIN"}
          </button>
        </form>

        <div className="login-divider">
          <span>OR</span>
        </div>

        <div className="social-login">
          {SOCIAL_PROVIDERS.map(({ name, Icon }) => (
            <button
              key={name}
              type="button"
              className="social-login-btn"
              onClick={() => handleSocial(name)}
            >
              <Icon />
              <span>Continue with {name}</span>
            </button>
          ))}
        </div>

        {note && (
          <p className="login-note" role="status">
            {note}
          </p>
        )}

        <p className="login-create">
          Don't have an account?{" "}
          <button
            type="button"
            className="login-link-inline"
            onClick={() => setNote(CREATE_MESSAGE)}
          >
            Create Account
          </button>
        </p>

        <div className="login-info">
          <span className="login-info-icon" aria-hidden="true">
            <ShieldIcon />
          </span>

          <span>
            Account registration will be available when backend authentication
            is connected.
          </span>
        </div>
      </div>
    </div>
  );
}

export default Login;
