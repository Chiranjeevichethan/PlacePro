from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


GoalCategory = Literal['skill', 'preparation', 'mock_test', 'profile', 'opportunity', 'weekly_target', 'other']
GoalPriority = Literal['high', 'medium', 'low']
GoalStatus = Literal['active', 'paused', 'completed']
GoalModule = Literal['readiness', 'skillgap', 'mocktests', 'performance', 'profile', 'companies', 'prediction']
MilestoneStatus = Literal['pending', 'completed']


class GoalInput(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=2000)
    category: GoalCategory = 'preparation'
    target_date: date | None = None
    priority: GoalPriority = 'medium'
    related_module: GoalModule | None = None

    @field_validator('title')
    @classmethod
    def title_is_not_blank(cls, value):
        if not value:
            raise ValueError('A goal title is required.')
        return value


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category: GoalCategory | None = None
    target_date: date | None = None
    priority: GoalPriority | None = None
    status: GoalStatus | None = None
    related_module: GoalModule | None = None

    @field_validator('title')
    @classmethod
    def title_is_not_blank(cls, value):
        if value is not None and not value:
            raise ValueError('A goal title is required.')
        return value

    @model_validator(mode='after')
    def fields_are_present_and_non_null(self):
        if not self.model_fields_set:
            raise ValueError('At least one goal field must be supplied.')
        if any(getattr(self, name) is None for name in self.model_fields_set
               if name not in {'target_date', 'related_module'}):
            raise ValueError('Use an empty string to clear description; required fields cannot be null.')
        return self


class MilestoneInput(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=1000)
    target_date: date | None = None

    @field_validator('title')
    @classmethod
    def title_is_not_blank(cls, value):
        if not value:
            raise ValueError('A milestone title is required.')
        return value


class MilestoneUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    target_date: date | None = None
    status: MilestoneStatus | None = None

    @field_validator('title')
    @classmethod
    def title_is_not_blank(cls, value):
        if value is not None and not value:
            raise ValueError('A milestone title is required.')
        return value

    @model_validator(mode='after')
    def fields_are_present_and_non_null(self):
        if not self.model_fields_set:
            raise ValueError('At least one milestone field must be supplied.')
        if any(getattr(self, name) is None for name in self.model_fields_set if name != 'target_date'):
            raise ValueError('Use an empty string to clear description; required fields cannot be null.')
        return self
