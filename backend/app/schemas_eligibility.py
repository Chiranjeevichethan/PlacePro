# ============================================================
# PLACEPRO - PHASE 13 - COMPANY ELIGIBILITY SCHEMAS
# ============================================================
#
# Response models for:
#   GET /api/companies
#   GET /api/companies/{company_id}
#   GET /api/profile/{profile_id}/eligibility
#   GET /api/profile/{profile_id}/eligibility/{company_id}
#
# ============================================================

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class CompanySummary(BaseModel):
    company_id: str
    company_name: str
    industry: Optional[str] = None
    roles: List[str] = Field(default_factory=list)


class CompanyDetail(CompanySummary):
    active: bool = True
    requirements: Dict[str, Any] = Field(default_factory=dict)


class RequirementResult(BaseModel):
    """One PASS / FAIL / UNKNOWN requirement check."""

    requirement: str
    student_value: Optional[Union[float, int, str]] = None
    required_value: Optional[Union[float, int, str, List[Union[int, str]]]] = None
    status: str  # PASS / FAIL / UNKNOWN
    mandatory: bool = True
    explanation: str
    action: Optional[str] = None


class RequirementGroups(BaseModel):
    passed: List[RequirementResult] = Field(default_factory=list)
    failed: List[RequirementResult] = Field(default_factory=list)
    unknown: List[RequirementResult] = Field(default_factory=list)


class CompanyEligibilityResponse(BaseModel):
    """Transparent eligibility of one profile for one company.

    `status` is ELIGIBLE / NOT_ELIGIBLE / INCOMPLETE and is driven
    ONLY by company requirements - never by ML placement probability.
    """

    company_id: str
    company_name: str
    status: str
    requirements: RequirementGroups
    missing_information: List[str] = Field(default_factory=list)
    explanation: List[str] = Field(default_factory=list)


class CompanyEligibilitySummary(BaseModel):
    company: CompanySummary
    status: str
    passed_count: int = 0
    failed_count: int = 0
    unknown_count: int = 0
    major_reasons: List[str] = Field(default_factory=list)


class AllCompanyEligibilityResponse(BaseModel):
    eligible: List[CompanyEligibilitySummary] = Field(default_factory=list)
    not_eligible: List[CompanyEligibilitySummary] = Field(default_factory=list)
    incomplete: List[CompanyEligibilitySummary] = Field(default_factory=list)
