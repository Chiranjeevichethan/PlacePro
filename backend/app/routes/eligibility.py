# ============================================================
# PLACEPRO - PHASE 13 - COMPANY ELIGIBILITY ROUTES
# ============================================================
#
#   GET /api/companies
#       -> active demo companies (summaries)
#   GET /api/companies/{company_id}
#       -> one company's requirements
#   GET /api/profile/{profile_id}/eligibility/{company_id}
#       -> transparent eligibility of a verified profile
#          for one company
#   GET /api/profile/{profile_id}/eligibility
#       -> eligibility against all active companies
#
# Company data comes ONLY from the configured server-side company
# store (Phase 28C: SQLite via backend/app/services/company_store.py,
# seeded from backend/app/data/companies.py) - clients cannot modify
# requirements or supply company files.
#
# ============================================================

from typing import List

from fastapi import APIRouter, HTTPException

from ..schemas_eligibility import (
    AllCompanyEligibilityResponse,
    CompanyDetail,
    CompanyEligibilityResponse,
    CompanySummary,
)
from ..services.eligibility_service import (
    CompanyNotFoundError,
    EligibilityServiceError,
    get_all_eligibility,
    get_company_detail,
    get_eligibility,
    list_companies,
)
from ..services.profile_service import ProfileServiceError

router = APIRouter(tags=["eligibility"])


@router.get(
    "/api/companies",
    response_model=List[CompanySummary],
    summary="List active demo companies",
)
def companies_list():
    """Return the active demo companies (SAMPLE requirements)."""
    return list_companies()


@router.get(
    "/api/companies/{company_id}",
    response_model=CompanyDetail,
    summary="Get one company's requirements",
)
def companies_detail(company_id: str):
    """Return one company's configured requirements."""
    try:
        return get_company_detail(company_id)
    except CompanyNotFoundError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/api/profile/{profile_id}/eligibility/{company_id}",
    response_model=CompanyEligibilityResponse,
    summary="Eligibility of a verified profile for one company",
)
def profile_eligibility(profile_id: str, company_id: str):
    """Transparent PASS/FAIL/UNKNOWN eligibility analysis.

    - profile must exist (404) and be verified (422)
    - company must exist (404)
    - eligibility is based ONLY on company requirements - never on
      ML placement probability
    - missing information is UNKNOWN, never treated as failure
    """
    try:
        return get_eligibility(profile_id, company_id)
    except (ProfileServiceError, EligibilityServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Eligibility check failed: {exc}"
        ) from exc


@router.get(
    "/api/profile/{profile_id}/eligibility",
    response_model=AllCompanyEligibilityResponse,
    summary="Eligibility of a verified profile against all companies",
)
def profile_all_eligibility(profile_id: str):
    """Eligibility against every active company, grouped by status."""
    try:
        return get_all_eligibility(profile_id)
    except (ProfileServiceError, EligibilityServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Eligibility check failed: {exc}"
        ) from exc
