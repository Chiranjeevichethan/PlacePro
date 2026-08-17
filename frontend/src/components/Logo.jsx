import { useId } from "react";

/**
 * LogoMark - PlacePro symbol (reference logo system).
 * Stylized P with graduation cap, cyan analytics bars, and rising trend arrow.
 */
function LogoMark({ size = 40, className = "" }) {
  const rawId = useId();
  const safeId = rawId.replace(/[^a-zA-Z0-9]/g, "");
  const gradId = `placepro-p-${safeId}`;
  const capGradId = `placepro-cap-${safeId}`;

  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="PlacePro logo"
      focusable="false"
    >
      <defs>
        <linearGradient id={gradId} x1="8" y1="6" x2="56" y2="62" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="35%" stopColor="#2563EB" />
          <stop offset="100%" stopColor="#7C3AED" />
        </linearGradient>
        <linearGradient id={capGradId} x1="14" y1="8" x2="50" y2="28" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#3B82F6" />
          <stop offset="100%" stopColor="#7C3AED" />
        </linearGradient>
      </defs>

      {/* Letter P stem and bowl */}
      <path
        d="M22 30 V58 M22 30 H44 a12 12 0 0 1 0 24 H22"
        fill="none"
        stroke={`url(#${gradId})`}
        strokeWidth="11"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Stem cutouts */}
      <rect x="18.5" y="38" width="7" height="3.8" rx="1.9" fill="#ffffff" opacity="0.95" />
      <rect x="18.5" y="46.5" width="7" height="3.8" rx="1.9" fill="#ffffff" opacity="0.95" />

      {/* Analytics bars inside bowl */}
      <rect x="42" y="44" width="3.2" height="6" rx="1.6" fill="#22D3EE" />
      <rect x="46.8" y="40" width="3.2" height="10" rx="1.6" fill="#22D3EE" />
      <rect x="51.6" y="36" width="3.2" height="14" rx="1.6" fill="#06B6D4" />

      {/* Rising trend arrow */}
      <path
        d="M54.5 47 C 58.5 40, 57 33, 50 30.5"
        fill="none"
        stroke="#22D3EE"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <path
        d="M50 30.5 l-3.2 2.6 M50 30.5 l1.4 3.8"
        fill="none"
        stroke="#22D3EE"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Graduation cap */}
      <polygon points="12,18 32,10 52,18 32,26" fill={`url(#${capGradId})`} />
      <circle cx="32" cy="14" r="1.8" fill="#ffffff" />
      <rect x="22" y="24" width="20" height="6.5" rx="2" fill={`url(#${capGradId})`} />

      {/* Tassel */}
      <path
        d="M22 29 C 17 34, 15 39, 16.5 44"
        fill="none"
        stroke="#22D3EE"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="16.8" cy="46" r="2.2" fill="#7C3AED" />
    </svg>
  );
}

/**
 * IconTile - favicon-style rounded square with white mark on gradient.
 */
function IconTile({ size = 40, className = "" }) {
  const rawId = useId();
  const safeId = rawId.replace(/[^a-zA-Z0-9]/g, "");
  const bgId = `placepro-bg-${safeId}`;

  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="PlacePro"
      focusable="false"
    >
      <defs>
        <linearGradient id={bgId} x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#2563EB" />
          <stop offset="100%" stopColor="#7C3AED" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="15" fill={`url(#${bgId})`} />
      <polygon points="12,18 32,10 52,18 32,26" fill="#ffffff" />
      <circle cx="32" cy="14" r="1.6" fill="#2563EB" />
      <rect x="22" y="24" width="20" height="6.5" rx="2" fill="#ffffff" />
      <path
        d="M22 30 V58 M22 30 H44 a12 12 0 0 1 0 24 H22"
        fill="none"
        stroke="#ffffff"
        strokeWidth="10"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="42" y="44" width="3" height="6" rx="1.5" fill="#22D3EE" />
      <rect x="46.8" y="40" width="3" height="10" rx="1.5" fill="#22D3EE" />
      <rect x="51.6" y="36" width="3" height="14" rx="1.5" fill="#22D3EE" />
      <path
        d="M54.5 47 C 58 40, 56.5 33, 50 30.5 M50 30.5 l-2.8 2.4 M50 30.5 l1.2 3.6"
        fill="none"
        stroke="#22D3EE"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function LogoWordmark({ showTag = true, className = "" }) {
  return (
    <div className={`placepro-logo-text ${className}`}>
      <span className="placepro-logo-name">
        PLACE<span className="placepro-logo-name-accent">PRO</span>
      </span>
      {showTag && (
        <span className="placepro-logo-tag">AI Placement Prediction System</span>
      )}
    </div>
  );
}

/**
 * variants:
 *  - full     : mark + wordmark + tag (navbar)
 *  - compact  : mark + wordmark
 *  - sidebar  : mark + wordmark + tag (sidebar branding)
 *  - stacked  : mark above wordmark (login)
 *  - icon     : mark only
 *  - tile     : rounded gradient tile (favicon-style)
 */
function Logo({ variant = "full", size = 40, className = "" }) {
  if (variant === "icon") {
    return <LogoMark size={size} className={className} />;
  }

  if (variant === "tile") {
    return <IconTile size={size} className={className} />;
  }

  if (variant === "stacked") {
    return (
      <div className={`placepro-logo placepro-logo-stacked logo-${variant} ${className}`}>
        <LogoMark size={size} className="placepro-logo-mark placepro-logo-mark-stacked" />
        <LogoWordmark showTag />
      </div>
    );
  }

  const showTag = variant === "full" || variant === "sidebar";

  return (
    <div className={`placepro-logo logo-${variant} ${className}`}>
      <LogoMark size={size} className="placepro-logo-mark" />
      <LogoWordmark showTag={showTag} />
    </div>
  );
}

export default Logo;
