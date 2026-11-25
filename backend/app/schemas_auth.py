"""Auth-only validation; errors must be projected without submitted inputs."""
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from .services.account_validation import normalize_account_email, validate_password


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    minimum_password_length: ClassVar[int] = 1
    email: str
    password: SecretStr

    @field_validator("email", mode="before")
    @classmethod
    def email_policy(cls, value):
        return normalize_account_email(value)

    @field_validator("password", mode="before")
    @classmethod
    def password_policy(cls, value):
        return validate_password(value, minimum=cls.minimum_password_length)


class RegistrationRequest(LoginRequest):
    minimum_password_length: ClassVar[int] = 15


class RegistrationResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    message: str = "Registration request received. Email verification is required; verification delivery is not available yet."
