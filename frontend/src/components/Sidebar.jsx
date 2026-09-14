import IconMark from "./IconMark";
import Logo from "./Logo";

const menuItems = [
  { page: "dashboard", label: "Dashboard", icon: "dashboard" },
  { page: "prediction", label: "Placement Prediction", icon: "prediction" },
  { page: "salary", label: "Salary Prediction", icon: "salary" },
  { page: "companies", label: "Company Recommendations", icon: "company" },
  { page: "skillgap", label: "Skill Gap Analysis", icon: "skills" },
  { page: "mocktests", label: "Mock Tests", icon: "mocktest" },
  { page: "profile", label: "Student Profile", icon: "profile" },
  { page: "performance", label: "Performance Analysis", icon: "performance" },
  { page: "about", label: "About", icon: "about" },
];

function Sidebar({ currentPage, setCurrentPage }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <Logo variant="sidebar" size={36} />
      </div>

      <div className="sidebar-title">MENU</div>

      <nav className="sidebar-menu" aria-label="Primary navigation">
        {menuItems.map((item) => (
          <a
            key={item.page}
            href="#"
            className={currentPage === item.page ? "active" : ""}
            aria-current={currentPage === item.page ? "page" : undefined}
            onClick={(e) => {
              e.preventDefault();
              setCurrentPage(item.page);
            }}
          >
            <IconMark name={item.icon} className="sidebar-icon" />
            <span>{item.label}</span>
          </a>
        ))}
      </nav>

      <div className="sidebar-ai-card">
        <svg
          className="ai-card-art"
          viewBox="0 0 120 64"
          role="presentation"
          aria-hidden="true"
        >
          <g className="ai-card-lines">
            <line x1="18" y1="40" x2="42" y2="18" />
            <line x1="42" y1="18" x2="70" y2="26" />
            <line x1="70" y1="26" x2="96" y2="14" />
            <line x1="42" y1="18" x2="60" y2="44" />
            <line x1="60" y1="44" x2="96" y2="14" />
            <line x1="60" y1="44" x2="104" y2="48" />
            <line x1="18" y1="40" x2="60" y2="44" />
          </g>
          <g className="ai-card-nodes">
            <circle cx="18" cy="40" r="3" />
            <circle cx="42" cy="18" r="3.5" />
            <circle cx="70" cy="26" r="2.5" />
            <circle cx="96" cy="14" r="3" />
            <circle cx="60" cy="44" r="3.5" />
            <circle cx="104" cy="48" r="2.5" />
          </g>
        </svg>

        <div className="ai-card-copy">
          <strong>Predict • Prepare • Place</strong>
          <span>
            Your Future,
            <br />
            Powered by AI
          </span>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
