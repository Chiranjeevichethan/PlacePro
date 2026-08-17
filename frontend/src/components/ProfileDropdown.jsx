import { useEffect, useRef, useState } from "react";

function readProfileName() {
  try {
    const raw = localStorage.getItem("placepro_profile");
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.name) return parsed.name;
    }
  } catch {
    // Fall back to the default name below.
  }
  return "Bhargav";
}

function UserIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

function ProfileDropdown({ onNavigate, onEditProfile, onLogout }) {
  const [userName, setUserName] = useState(readProfileName);
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const syncName = () => setUserName(readProfileName());
    window.addEventListener("storage", syncName);
    window.addEventListener("placepro-profile-updated", syncName);
    return () => {
      window.removeEventListener("storage", syncName);
      window.removeEventListener("placepro-profile-updated", syncName);
    };
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setShowMenu(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const close = () => setShowMenu(false);

  const avatarLetter = userName ? userName.charAt(0).toUpperCase() : "B";

  return (
    <div className="navbar-user" ref={menuRef}>
      <button
        type="button"
        className="navbar-user-trigger"
        onClick={() => setShowMenu((prev) => !prev)}
        aria-expanded={showMenu}
        aria-haspopup="menu"
      >
        <span className="user-trigger-text">
          <strong>{userName}</strong>
          <small>Student</small>
        </span>

        <span className="user-avatar" aria-hidden="true">
          {avatarLetter}
        </span>

        <svg
          className="user-trigger-chevron"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {showMenu && (
        <div className="user-menu" role="menu">
          <div className="user-menu-header">
            <div className="user-menu-avatar">{avatarLetter}</div>

            <div>
              <strong>{userName}</strong>
              <small>Student</small>
            </div>
          </div>

          <div className="user-menu-divider" />

          <button
            type="button"
            className="user-menu-item"
            onClick={() => {
              onNavigate("profile");
              close();
            }}
            role="menuitem"
          >
            <span className="menu-item-icon">
              <UserIcon />
            </span>
            <span>Student Profile</span>
          </button>

          <button
            type="button"
            className="user-menu-item"
            onClick={() => {
              onEditProfile();
              close();
            }}
            role="menuitem"
          >
            <span className="menu-item-icon edit">
              <EditIcon />
            </span>
            <span>Edit Profile</span>
          </button>

          <div className="user-menu-divider" />

          <button
            type="button"
            className="user-menu-item logout-item"
            onClick={() => {
              onLogout();
              close();
            }}
            role="menuitem"
          >
            <span className="menu-item-icon logout">
              <LogoutIcon />
            </span>
            <span>Logout</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default ProfileDropdown;
