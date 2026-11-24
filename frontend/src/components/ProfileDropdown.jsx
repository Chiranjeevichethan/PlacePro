import { useEffect, useRef, useState } from "react";
import { useStudentProfileContext } from "../hooks/useStudentProfileContext";
import { appHrefForPage, handleAppLinkClick } from "../services/appRoutes.js";

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

function ProfileDropdown({ currentPage, onNavigate, onEditProfile, onLogout, logoutBusy }) {
  /* Name comes from the ONE canonical profile — no hardcoded fallback name
     and no stale localStorage value. */
  const { profile } = useStudentProfileContext();
  const userName = profile?.name?.trim() || "Student";
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef(null);
  const triggerRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setShowMenu(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!showMenu) return;
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setShowMenu(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [showMenu]);

  const close = () => setShowMenu(false);

  const avatarLetter = userName.charAt(0).toUpperCase();

  return (
    <div className="navbar-user" ref={menuRef}>
      <button
        type="button"
        className="navbar-user-trigger"
        ref={triggerRef}
        onClick={() => setShowMenu((prev) => !prev)}
        aria-expanded={showMenu}
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
        <div className="user-menu" role="group" aria-label="Account actions">
          <div className="user-menu-header">
            <div className="user-menu-avatar">{avatarLetter}</div>

            <div>
              <strong>{userName}</strong>
              <small>Student</small>
            </div>
          </div>

          <div className="user-menu-divider" />

          <a
            href={appHrefForPage("profile")}
            className="user-menu-item"
            aria-current={currentPage === "profile" ? "page" : undefined}
            onClick={(event) => {
              handleAppLinkClick(event, "profile", onNavigate);
              if (event.defaultPrevented) close();
            }}
          >
            <span className="menu-item-icon">
              <UserIcon />
            </span>
            <span>Student Profile</span>
          </a>

          <button
            type="button"
            className="user-menu-item"
            onClick={() => {
              onEditProfile();
              close();
            }}
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
            disabled={logoutBusy}
            onClick={() => {
              onLogout();
              close();
            }}
          >
            <span className="menu-item-icon logout">
              <LogoutIcon />
            </span>
            <span>{logoutBusy ? 'Signing out…' : 'Logout'}</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default ProfileDropdown;
