# ============================================================
# PLACEPRO - PHASE 28C - SQLITE COMPANY STORE
# ============================================================
#
# SQLite-backed store for companies and versioned requirement sets,
# behind a service API that mirrors the access pattern the Phase 13
# eligibility and Phase 14 recommendation engines already use:
#
#     get_active_companies() / get_company(company_id)
#
# so the engines keep their exact behavior while the data source
# changes from an in-memory list to a database.
#
# DESIGN RULES
#   - Python stdlib sqlite3 only (no new dependency).
#   - The database is initialized automatically on first use and
#     seeded from backend/app/data/companies.py ONLY when empty.
#     Seeding is idempotent and deterministic.
#   - Every requirement field is stored per-row with an explicit
#     `provided` flag. A requirement that was never provided is
#     stored as provided=0 with a NULL value - it can never come
#     back out as a guessed cutoff. Downstream, provided=0 fields
#     are simply absent from the company dict, which preserves the
#     existing Phase 13 semantics (absent = not evaluated /
#     UNKNOWN, never FAIL).
#   - Requirement sets are VERSIONED (one company may have many
#     sets across recruitment cycles). get_company() resolves the
#     active set deterministically: prefer VERIFIED > UNVERIFIED >
#     DEMO, then latest verified_at, then lexicographically last
#     requirement_set_id. The DEMO seed has exactly one set per
#     company, so current behavior is unchanged.
#   - Company dicts are enriched with provenance metadata from the
#     active requirement set (source_type, source_url, verified_at,
#     verified_by, verification_status, recruitment_cycle, notes)
#     under the key "requirement_set".
#   - Rows are always read in deterministic order (ORDER BY).
#
# HONESTY
#   - The DEMO seed is labeled verification_status="DEMO" end to
#     end. Demo companies are never presented as real.
#   - Weights / threshold of the recommendation engine are NOT
#     touched here and remain documented heuristics, NOT empirically
#     validated values.
#
# ============================================================

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

# ------------------------------------------------------------
# LOCATION / CONNECTION
# ------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, "data", "companies.db")

# Overridable for tests (mirrors PLACEPRO_PROFILES_DIR convention).
DB_PATH = os.environ.get("PLACEPRO_COMPANIES_DB") or DEFAULT_DB_PATH

_lock = threading.RLock()

# The 10 requirement fields (exact Phase 13 field names).
REQUIREMENT_FIELDS = (
    "min_cgpa",
    "max_backlogs",
    "allowed_branches",
    "allowed_graduation_years",
    "required_skills",
    "preferred_skills",
    "min_internships",
    "min_projects",
    "min_certifications",
    "min_aptitude_score",
)

# Requirement fields whose value is stored as JSON (lists etc.).
_JSON_FIELDS = frozenset({
    "allowed_branches",
    "allowed_graduation_years",
    "required_skills",
    "preferred_skills",
})

# Provenance enums (Phase 28B design).
SOURCE_TYPES = frozenset({
    "OFFICIAL_CAREERS",
    "OFFICIAL_JOB_DESCRIPTION",
    "PLACEMENT_CELL_DOCUMENT",
    "OTHER_PUBLIC_SOURCE",
    "DEMO",
})
VERIFICATION_STATUSES = frozenset({"VERIFIED", "UNVERIFIED", "DEMO"})

# Resolution preference for the active requirement set (lower wins).
_STATUS_RANK = {"VERIFIED": 0, "UNVERIFIED": 1, "DEMO": 2}


class CompanyStoreError(Exception):
    status_code = 422


class CompanyNotFoundError(CompanyStoreError):
    status_code = 404


# ------------------------------------------------------------
# SCHEMA
# ------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    company_id   TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    industry     TEXT,
    roles        TEXT NOT NULL DEFAULT '[]',   -- JSON array
    locations    TEXT NOT NULL DEFAULT '[]',   -- JSON array
    active       INTEGER NOT NULL DEFAULT 1,
    notes        TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requirement_sets (
    requirement_set_id  TEXT PRIMARY KEY,
    company_id          TEXT NOT NULL REFERENCES companies(company_id),
    recruitment_cycle   TEXT,
    source_type         TEXT NOT NULL,
    source_url          TEXT,
    verified_at         TEXT,
    verified_by         TEXT,
    verification_status TEXT NOT NULL,
    notes               TEXT,
    created_at          TEXT NOT NULL,
    CHECK (source_type IN ('OFFICIAL_CAREERS', 'OFFICIAL_JOB_DESCRIPTION',
                           'PLACEMENT_CELL_DOCUMENT', 'OTHER_PUBLIC_SOURCE',
                           'DEMO')),
    CHECK (verification_status IN ('VERIFIED', 'UNVERIFIED', 'DEMO'))
);

CREATE TABLE IF NOT EXISTS requirements (
    requirement_set_id TEXT NOT NULL REFERENCES requirement_sets(requirement_set_id),
    field              TEXT NOT NULL,
    provided           INTEGER NOT NULL,       -- 1 = provided, 0 = explicitly absent
    value_json         TEXT,                   -- NULL when provided = 0
    PRIMARY KEY (requirement_set_id, field),
    CHECK (provided IN (0, 1)),
    -- A not-provided requirement must never carry a value (no guessed cutoffs).
    CHECK (provided = 1 OR value_json IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_requirement_sets_company
    ON requirement_sets(company_id);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------
# INITIALIZATION + SEEDING
# ------------------------------------------------------------

_initialized = False


def _seed_if_empty(conn: sqlite3.Connection) -> int:
    """Seed DEMO companies from data/companies.py when the DB is empty.

    Returns the number of companies seeded. Idempotent: existing rows
    are never modified, so manual/verified data can never be overwritten
    by a re-seed.
    """
    from ..data.companies import seed_demo_companies

    count = conn.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"]
    if count:
        return 0

    now = _now_iso()
    seeded = 0
    for company in seed_demo_companies():
        _insert_company(conn, company, now)
        seeded += 1
    conn.commit()
    return seeded


def _insert_company(conn: sqlite3.Connection, company: dict, now: str) -> None:
    """Insert one company + its active requirement set + requirement rows."""
    company_id = company["company_id"]
    conn.execute(
        """
        INSERT INTO companies
            (company_id, company_name, industry, roles, locations,
             active, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            company["company_name"],
            company.get("industry"),
            json.dumps(list(company.get("roles") or [])),
            json.dumps(list(company.get("locations") or [])),
            1 if company.get("active", True) else 0,
            company.get("notes"),
            now,
            now,
        ),
    )

    meta = dict(company.get("requirement_set") or {})
    set_id = meta.get("requirement_set_id") or f"{company_id}_v1"
    source_type = meta.get("source_type") or "DEMO"
    verification_status = meta.get("verification_status") or "DEMO"
    if source_type not in SOURCE_TYPES:
        raise CompanyStoreError(f"Invalid source_type '{source_type}'.")
    if verification_status not in VERIFICATION_STATUSES:
        raise CompanyStoreError(
            f"Invalid verification_status '{verification_status}'."
        )

    conn.execute(
        """
        INSERT INTO requirement_sets
            (requirement_set_id, company_id, recruitment_cycle, source_type,
             source_url, verified_at, verified_by, verification_status,
             notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            set_id,
            company_id,
            meta.get("recruitment_cycle"),
            source_type,
            meta.get("source_url"),
            meta.get("verified_at"),
            meta.get("verified_by"),
            verification_status,
            meta.get("notes"),
            now,
        ),
    )

    requirements = company.get("requirements") or {}
    for field in REQUIREMENT_FIELDS:
        if field in requirements:
            value = requirements[field]
            if value is None:
                # Explicit null is treated as not provided (never a guessed value).
                provided, value_json = 0, None
            else:
                provided, value_json = 1, json.dumps(value)
        else:
            provided, value_json = 0, None
        conn.execute(
            """
            INSERT INTO requirements (requirement_set_id, field, provided, value_json)
            VALUES (?, ?, ?, ?)
            """,
            (set_id, field, provided, value_json),
        )


def initialize() -> None:
    """Create the schema and seed the DEMO companies (once per process)."""
    global _initialized
    with _lock:
        if _initialized:
            return
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        conn = _connect()
        try:
            conn.executescript(_SCHEMA)
            _seed_if_empty(conn)
        finally:
            conn.close()
        _initialized = True


def reset_for_tests(path: str) -> None:
    """Test helper: point the store at a fresh file and (re)initialize.

    The module-level DB_PATH is rebound so subsequent calls in this
    process use the test database.
    """
    global DB_PATH, _initialized
    with _lock:
        DB_PATH = path
        _initialized = False
        initialize()


# ------------------------------------------------------------
# ROW -> DICT MAPPING
# ------------------------------------------------------------
# The engines consume the HISTORICAL dict shape:
#   {company_id, company_name, industry, roles, active, requirements}
# so provided=0 fields are simply absent from `requirements` - exactly
# like the previous flat demo dicts. Provenance is additive under
# "requirement_set" (new consumers may use it; old ones ignore it).


def _requirements_to_flat(requirement_set_id: str, conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT field, provided, value_json FROM requirements
        WHERE requirement_set_id = ?
        ORDER BY field
        """,
        (requirement_set_id,),
    ).fetchall()
    flat = {}
    for row in rows:
        if not row["provided"]:
            continue  # not provided -> absent (Phase 13: not evaluated)
        value = json.loads(row["value_json"]) if row["value_json"] is not None else None
        flat[row["field"]] = value
    return flat


def _set_meta_to_dict(row: sqlite3.Row) -> dict:
    return {
        "requirement_set_id": row["requirement_set_id"],
        "recruitment_cycle": row["recruitment_cycle"],
        "source_type": row["source_type"],
        "source_url": row["source_url"],
        "verified_at": row["verified_at"],
        "verified_by": row["verified_by"],
        "verification_status": row["verification_status"],
        "notes": row["notes"],
    }


_ACTIVE_SET_ORDER = (
    "ORDER BY CASE verification_status "
    "WHEN 'VERIFIED' THEN 0 WHEN 'UNVERIFIED' THEN 1 ELSE 2 END, "
    "COALESCE(verified_at, '') DESC, requirement_set_id DESC LIMIT 1"
)


def _company_from_row(company_row: sqlite3.Row,
                      set_row: sqlite3.Row,
                      conn: sqlite3.Connection) -> dict:
    company = {
        "company_id": company_row["company_id"],
        "company_name": company_row["company_name"],
        "industry": company_row["industry"],
        "roles": json.loads(company_row["roles"]),
        "locations": json.loads(company_row["locations"]),
        "active": bool(company_row["active"]),
        "notes": company_row["notes"],
        "requirements": _requirements_to_flat(set_row["requirement_set_id"], conn),
        "requirement_set": _set_meta_to_dict(set_row),
    }
    return company


def _active_set_row(company_id: str, conn: sqlite3.Connection):
    return conn.execute(
        f"""
        SELECT * FROM requirement_sets
        WHERE company_id = ?
        {_ACTIVE_SET_ORDER}
        """,
        (company_id,),
    ).fetchone()


# ------------------------------------------------------------
# PUBLIC ACCESSORS (engine-facing, stable API)
# ------------------------------------------------------------


def get_active_companies() -> list:
    """All active companies with their active requirement set.

    Deterministic: ordered by company_id. Dict shape matches the
    historical demo dicts (plus additive `locations`, `notes` and
    `requirement_set` provenance).
    """
    initialize()
    conn = _connect()
    try:
        company_rows = conn.execute(
            """
            SELECT * FROM companies WHERE active = 1 ORDER BY company_id
            """
        ).fetchall()
        companies = []
        for company_row in company_rows:
            set_row = _active_set_row(company_row["company_id"], conn)
            if set_row is None:
                continue  # a company without any requirement set is not usable
            companies.append(_company_from_row(company_row, set_row, conn))
        return companies
    finally:
        conn.close()


def get_company(company_id: str):
    """One company by id (active or not), or None - mirrors the old contract."""
    initialize()
    conn = _connect()
    try:
        company_row = conn.execute(
            "SELECT * FROM companies WHERE company_id = ?", (company_id,)
        ).fetchone()
        if company_row is None:
            return None
        set_row = _active_set_row(company_id, conn)
        if set_row is None:
            return None
        return _company_from_row(company_row, set_row, conn)
    finally:
        conn.close()


def get_requirement_set(company_id: str):
    """Provenance metadata of a company's active requirement set, or None.

    Includes verification fields (source_type / source_url / verified_at /
    verified_by / verification_status / recruitment_cycle / notes).
    """
    initialize()
    conn = _connect()
    try:
        set_row = _active_set_row(company_id, conn)
        return _set_meta_to_dict(set_row) if set_row is not None else None
    finally:
        conn.close()


def get_requirement_set_requirements(company_id: str) -> dict:
    """Per-field requirement view for a company's ACTIVE requirement set.

    Unlike the flat company dict, this exposes the provided flag
    explicitly:
        {field: {"provided": bool, "value": value-or-None}}
    All 10 canonical fields are always present. Returns {} when the
    company (or any requirement set for it) does not exist.
    """
    initialize()
    conn = _connect()
    try:
        set_row = _active_set_row(company_id, conn)
        if set_row is None:
            return {}
        rows = conn.execute(
            """
            SELECT field, provided, value_json FROM requirements
            WHERE requirement_set_id = ?
            ORDER BY field
            """,
            (set_row["requirement_set_id"],),
        ).fetchall()
        by_field = {row["field"]: row for row in rows}
        result = {}
        for field in REQUIREMENT_FIELDS:
            row = by_field.get(field)
            if row is None or not row["provided"]:
                result[field] = {"provided": False, "value": None}
            else:
                value = (
                    json.loads(row["value_json"])
                    if row["value_json"] is not None else None
                )
                result[field] = {"provided": True, "value": value}
        return result
    finally:
        conn.close()


def count_companies(active_only: bool = False) -> int:
    """Number of companies in the store (diagnostics/tests)."""
    initialize()
    conn = _connect()
    try:
        if active_only:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM companies WHERE active = 1"
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS n FROM companies").fetchone()
        return int(row["n"])
    finally:
        conn.close()
