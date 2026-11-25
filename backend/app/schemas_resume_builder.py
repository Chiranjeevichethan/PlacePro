"""Validated, profile-owned student-authored resume documents."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Source = Literal['profile', 'student']
Section = Literal['summary', 'education', 'skills', 'projects', 'experience', 'internships',
                  'certifications', 'achievements']
ShortText = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True, str_strip_whitespace=True)


class ResumePersonal(StrictModel):
    name: ShortText = Field(default='', max_length=120)
    email: ShortText = Field(default='', max_length=254)
    phone: ShortText = Field(default='', max_length=64)
    location: ShortText = Field(default='', max_length=160)
    linkedin: ShortText = Field(default='', max_length=300)
    github: ShortText = Field(default='', max_length=300)
    portfolio: ShortText = Field(default='', max_length=300)


class Entry(StrictModel):
    entry_id: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    source: Source = 'student'


class EducationEntry(Entry):
    institution: str = Field(default='', max_length=180)
    degree: str = Field(default='', max_length=160)
    field: str = Field(default='', max_length=160)
    location: str = Field(default='', max_length=160)
    start_date: str = Field(default='', max_length=40)
    end_date: str = Field(default='', max_length=40)
    details: str = Field(default='', max_length=1000)


class SkillEntry(Entry):
    name: str = Field(min_length=1, max_length=100)
    group: str = Field(default='', max_length=80)


class ProjectEntry(Entry):
    title: str = Field(default='', max_length=180)
    description: str = Field(default='', max_length=2000)
    technologies: str = Field(default='', max_length=500)
    link: str = Field(default='', max_length=300)


class ExperienceEntry(Entry):
    organization: str = Field(default='', max_length=180)
    role: str = Field(default='', max_length=160)
    location: str = Field(default='', max_length=160)
    start_date: str = Field(default='', max_length=40)
    end_date: str = Field(default='', max_length=40)
    description: str = Field(default='', max_length=2000)


class CertificationEntry(Entry):
    name: str = Field(default='', max_length=180)
    issuer: str = Field(default='', max_length=180)
    date: str = Field(default='', max_length=40)


class AchievementEntry(Entry):
    title: str = Field(default='', max_length=180)
    description: str = Field(default='', max_length=1000)


class ResumeDocument(StrictModel):
    revision: int = Field(ge=0, strict=True)
    template: Literal['classic', 'modern'] = 'classic'
    section_order: list[Section] = Field(default_factory=lambda: [
        'summary', 'education', 'skills', 'projects', 'experience', 'internships', 'certifications', 'achievements',
    ], min_length=8, max_length=8)
    visible_sections: list[Section] = Field(default_factory=lambda: [
        'summary', 'education', 'skills', 'projects', 'experience', 'internships', 'certifications', 'achievements',
    ], max_length=8)
    personal: ResumePersonal = Field(default_factory=ResumePersonal)
    summary: str = Field(default='', max_length=3000)
    education: list[EducationEntry] = Field(default_factory=list, max_length=30)
    skills: list[SkillEntry] = Field(default_factory=list, max_length=100)
    projects: list[ProjectEntry] = Field(default_factory=list, max_length=50)
    experience: list[ExperienceEntry] = Field(default_factory=list, max_length=50)
    internships: list[ExperienceEntry] = Field(default_factory=list, max_length=50)
    certifications: list[CertificationEntry] = Field(default_factory=list, max_length=50)
    achievements: list[AchievementEntry] = Field(default_factory=list, max_length=50)
    personal_sources: dict[str, Source] = Field(default_factory=dict, max_length=7)
    summary_source: Source = 'student'

    @model_validator(mode='after')
    def valid_section_configuration(self):
        expected = {'summary', 'education', 'skills', 'projects', 'experience', 'internships', 'certifications', 'achievements'}
        if len(set(self.section_order)) != len(expected) or set(self.section_order) != expected:
            raise ValueError('Resume section order must contain each supported section exactly once.')
        if len(set(self.visible_sections)) != len(self.visible_sections):
            raise ValueError('Visible resume sections must be unique.')
        if not set(self.visible_sections).issubset(expected):
            raise ValueError('A visible resume section is unsupported.')
        if not set(self.personal_sources).issubset({'name', 'email', 'phone', 'location', 'linkedin', 'github', 'portfolio'}):
            raise ValueError('A personal field source is unsupported.')
        return self
