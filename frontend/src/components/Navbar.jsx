import Logo from "./Logo";
import SearchBar from "./SearchBar";
import ProfileDropdown from "./ProfileDropdown";

function Navbar({ setCurrentPage, onEditProfile, onLogout }) {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <Logo variant="compact" size={36} />
      </div>

      <SearchBar onNavigate={setCurrentPage} />

      <button
        type="button"
        className="navbar-bell"
        aria-label="Notifications"
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
        <span className="bell-badge" aria-hidden="true">
          3
        </span>
      </button>

      <ProfileDropdown
        onNavigate={setCurrentPage}
        onEditProfile={onEditProfile}
        onLogout={onLogout}
      />
    </nav>
  );
}

export default Navbar;
