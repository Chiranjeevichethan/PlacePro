import { useEffect, useRef, useState } from "react";

const SEARCH_PAGES = [
  {
    page: "dashboard",
    label: "Dashboard",
    keywords: "home overview analytics kpi statistics",
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

function SearchBar({ onNavigate }) {
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

    if (!showDropdown) {
      if ((event.key === "ArrowDown" || event.key === "Enter") && trimmed) {
        event.preventDefault();
        setOpen(true);
        setActiveIndex(0);
      }
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex(
        (index) => (index - 1 + results.length) % results.length
      );
    } else if (event.key === "Enter") {
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

        <input
          className="search-input"
          type="text"
          placeholder="Search pages..."
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActiveIndex(0);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          role="combobox"
          aria-label="Search PlacePro pages"
          aria-expanded={showDropdown}
          aria-controls="placepro-search-results"
          aria-activedescendant={
            showDropdown && activeIndex >= 0
              ? `search-result-${activeIndex}`
              : undefined
          }
          autoComplete="off"
        />

        {showDropdown && (
          <ul
            className="search-results"
            id="placepro-search-results"
            role="listbox"
            aria-label="Search results"
          >
            {results.length > 0 ? (
              results.map((item, index) => (
                <li
                  key={item.page}
                  role="option"
                  aria-selected={index === activeIndex}
                  id={`search-result-${index}`}
                >
                  <button
                    type="button"
                    className={`search-result-item ${
                      index === activeIndex ? "active" : ""
                    }`}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => selectPage(item.page)}
                  >
                    <span className="search-result-icon" aria-hidden="true">
                      <ArrowIcon />
                    </span>
                    <span className="search-result-label">{item.label}</span>
                  </button>
                </li>
              ))
            ) : (
              <li className="search-empty" role="option" aria-disabled="true">
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
