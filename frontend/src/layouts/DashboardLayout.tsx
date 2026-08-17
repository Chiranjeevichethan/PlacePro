import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
  { to: "/resume", label: "Resume", icon: "📄" },
  { to: "/profile", label: "Profile", icon: "👤" },
  { to: "/prediction", label: "Prediction", icon: "🎯" },
  { to: "/readiness", label: "Readiness", icon: "📈" },
  { to: "/assessment", label: "Assessment", icon: "📝" },
  { to: "/skills", label: "Skills", icon: "🧩" },
  { to: "/companies", label: "Companies", icon: "🏢" },
  { to: "/recommendations", label: "Recommendations", icon: "⭐" },
  { to: "/improvement-plan", label: "Improvement Plan", icon: "🛠️" },
];

export function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app-shell">
      <div className="topbar">
        <button
          className="hamburger"
          aria-label="Toggle navigation"
          onClick={() => setSidebarOpen((o) => !o)}
        >
          ☰
        </button>
        <strong>PlacePro</strong>
      </div>

      <div
        className={`sidebar-backdrop ${sidebarOpen ? "show" : ""}`}
        onClick={() => setSidebarOpen(false)}
      />

      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-brand">
          <div className="sidebar-logo">P</div>
          <div>
            <div className="brand-name">PlacePro</div>
            <div className="brand-sub">Student Dashboard</div>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
              onClick={() => setSidebarOpen(false)}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          Phase 18 · Student Dashboard
          <br />
          Demo mode (no auth yet)
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
