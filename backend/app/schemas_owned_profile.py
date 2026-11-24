"""Profile-only contracts; historical evidence stays deferred and stored unchanged."""
from pydantic import ConfigDict,Field
from .schemas_profile import StudentProfile,ProfileResponse,ProfileFromResumeResponse


class OwnedProfileRequest(StudentProfile):
    model_config=ConfigDict(extra='forbid',hide_input_in_errors=True)


class OwnedProfileView(StudentProfile):
    prediction_history: list=Field(default_factory=list,exclude=True)
    assessment_evidence: list=Field(default_factory=list,exclude=True)


class OwnedProfileResponse(ProfileResponse):
    profile: OwnedProfileView


class OwnedResumeResponse(ProfileFromResumeResponse):
    profile: OwnedProfileView
