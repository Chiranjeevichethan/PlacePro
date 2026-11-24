import Logo from "./Logo";
import SearchBar from "./SearchBar";
import ProfileDropdown from "./ProfileDropdown";
import OwnedProfileSelector from './OwnedProfileSelector';
import { appHrefForPage, handleAppLinkClick } from "../services/appRoutes.js";

function Navbar({ currentPage, setCurrentPage, onEditProfile, onLogout, onNewProfile, logoutBusy, unreadNotificationCount = null }) {
  return (
    <nav className="navbar" aria-label="Application controls">
      <div className="navbar-brand">
        <Logo variant="compact" size={36} />
      </div>

      <SearchBar currentPage={currentPage} onNavigate={setCurrentPage} />
      <OwnedProfileSelector onNewProfile={onNewProfile} />

      <a
        href={appHrefForPage("notifications")}
        className="navbar-bell"
        aria-current={currentPage === 'notifications' ? 'page' : undefined}
        aria-label={unreadNotificationCount === null ? 'Open notifications' : `Open notifications, ${unreadNotificationCount} unread`}
        title={unreadNotificationCount === null ? 'Notifications' : `${unreadNotificationCount} unread notifications`}
        onClick={(event) => handleAppLinkClick(event, 'notifications', setCurrentPage)}
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unreadNotificationCount > 0 && <span className="navbar-notification-count" aria-hidden="true">
          {unreadNotificationCount > 99 ? '99+' : unreadNotificationCount}
        </span>}
      </a>

      <ProfileDropdown
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        onEditProfile={onEditProfile}
        onLogout={onLogout}
        logoutBusy={logoutBusy}
      />
    </nav>
  );
}

export default Navbar;
