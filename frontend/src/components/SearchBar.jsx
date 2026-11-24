import { useEffect, useRef, useState } from "react";
import { appHrefForPage, handleAppLinkClick } from "../services/appRoutes.js";

const SEARCH_PAGES = [
  {
    page: "dashboard",
    label: "Dashboard",
    keywords: "home overview analytics kpi statistics",
  },
  {
    page: "readiness",
    label: "Career Readiness",
    keywords: "career prepare improvement plan profile completeness skills assessment",
  },
  {
    page: "goals",
    label: "Goals & Milestones",
    keywords: "goal goals milestone deadline target",
  },
  {
    page: "prediction",
    label: "Placement Prediction",
    keywords: "predict placement ai model form",
  },
  {
    page: "salary",
    label: "Salary Prediction",
    keywords: "salary prediction estimate lpa pay package ctc",
  },
  {
    page: "companies",
    label: "Company Recommendations",
    keywords: "company companies recommendations match jobs roles",
  },
  {
    page: "skillgap",
    label: "Skill Gap Analysis",
    keywords: "skill gap analysis learning resources target role",
  },
  {
    page: "mocktests",
    label: "Mock Tests",
    keywords: "mock test quiz practice questions python sql dbms networks operating systems aptitude",
  },
  {
    page: "profile",
    label: "Student Profile",
    keywords: "profile student edit details",
  },
  {
    page: "resume",
    label: "Resume Builder",
    keywords: "resume cv create edit export pdf portfolio",
  },
  {
    page: "performance",
    label: "Performance Analysis",
    keywords: "performance analysis scores strengths",
  },
  {
    page: "about",
    label: "About",
    keywords: "about project team technology stack machine learning",
  },
];

function SearchIcon({ className = "search-icon-svg" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

function SearchBar({ currentPage, onNavigate }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [mobileOpen, setMobileOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setOpen(false);
        setMobileOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const trimmed = query.trim().toLowerCase();

  const results = trimmed
    ? SEARCH_PAGES.filter(
        (page) =>
          page.label.toLowerCase().includes(trimmed) ||
          page.keywords.toLowerCase().includes(trimmed)
      )
    : SEARCH_PAGES;

  // Show the dropdown on focus even before typing, so all pages are
  // discoverable (dropdown was previously query-only).
  const showDropdown = open;

  const selectPage = (page) => {
    onNavigate(page);
    setQuery("");
    setOpen(false);
    setMobileOpen(false);
    setActiveIndex(-1);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Escape") {
      setOpen(false);
      setMobileOpen(false);
      setActiveIndex(-1);
      return;
    }

    if (!showDropdown && event.key === "Enter" && trimmed) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex(0);
      return;
    }

    if (showDropdown && event.key === "Enter") {
      event.preventDefault();
      if (results.length > 0) {
        const target = results[activeIndex >= 0 ? activeIndex : 0];
        selectPage(target.page);
      }
    }
  };

  return (
    <div
      className={`search-wrap ${mobileOpen ? "open" : ""}`}
      ref={wrapRef}
    >
      <button
        type="button"
        className="search-mobile-toggle"
        onClick={() => setMobileOpen((prev) => !prev)}
        aria-label="Open search"
        aria-expanded={mobileOpen}
      >
        <SearchIcon />
      </button>

      <div className="search-bar">
        <SearchIcon />

        <label className="visually-hidden" htmlFor="placepro-page-search">Search PlacePro pages</label>
        <input
          id="placepro-page-search"
          className="search-input"
          type="search"
          name="page-search"
          placeholder="Search pages..."
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActiveIndex(0);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          autoComplete="off"
        />

        {showDropdown && (
          <ul
            className="search-results"
            id="placepro-search-results"
            aria-label="Search results"
          >
            {results.length > 0 ? (
              results.map((item, index) => (
                <li
                  key={item.page}
                >
                  <a
                    href={appHrefForPage(item.page)}
                    className={`search-result-item ${
                      index === activeIndex ? "active" : ""
                    }`}
                    aria-current={currentPage === item.page ? "page" : undefined}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={(event) => handleAppLinkClick(event, item.page, selectPage)}
                  >
                    <span className="search-result-icon" aria-hidden="true">
                      <ArrowIcon />
                    </span>
                    <span className="search-result-label">{item.label}</span>
                  </a>
                </li>
              ))
            ) : (
              <li className="search-empty">
                No results found
              </li>
            )}
          </ul>
        )}
      </div>
    </div>
  );
}

export default SearchBar;
