"""Pydantic request/response models (the API contract)."""

from datetime import date, datetime
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.parsing import split_multi

T = TypeVar("T")

MULTI_VALUE_FIELDS = (
    "conditions",
    "interventions",
    "outcome_measures",
    "sponsors",
    "funded_by",
    "study_designs",
)


class TrialStatus(StrEnum):
    RECRUITING = "Recruiting"
    NOT_YET_RECRUITING = "Not yet recruiting"
    ACTIVE_NOT_RECRUITING = "Active, not recruiting"
    ENROLLING_BY_INVITATION = "Enrolling by invitation"
    COMPLETED = "Completed"
    SUSPENDED = "Suspended"
    TERMINATED = "Terminated"
    WITHDRAWN = "Withdrawn"
    AVAILABLE = "Available"
    NO_LONGER_AVAILABLE = "No longer available"
    TEMPORARILY_NOT_AVAILABLE = "Temporarily not available"
    APPROVED_FOR_MARKETING = "Approved for marketing"


class Gender(StrEnum):
    ALL = "All"
    FEMALE = "Female"
    MALE = "Male"


class AgeGroup(StrEnum):
    CHILD = "child"
    ADULT = "adult"
    OLDER_ADULT = "older_adult"


class SortField(StrEnum):
    START_DATE = "start_date"
    ENROLLMENT = "enrollment"
    FIRST_POSTED = "first_posted"
    LAST_UPDATE_POSTED = "last_update_posted"
    NCT_NUMBER = "nct_number"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


# --------------------------------------------------------------------------- locations


class LocationBase(BaseModel):
    facility: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=255)
    state: str | None = Field(None, max_length=255)
    country: str = Field(min_length=1, max_length=100)


class LocationRead(LocationBase):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- trials: input


class TrialFields(BaseModel):
    model_config = ConfigDict(use_enum_values=True, str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=2000)
    acronym: str | None = Field(None, max_length=100)
    status: TrialStatus
    has_results: bool = False
    conditions: list[str] = []
    interventions: list[str] = []
    outcome_measures: list[str] = []
    sponsors: list[str] = []
    funded_by: list[str] = []
    study_designs: list[str] = []
    gender: Gender | None = None
    age_description: str | None = Field(None, max_length=200)
    phases: str | None = Field(None, max_length=50)
    enrollment: int | None = Field(None, ge=0)
    study_type: str | None = Field(None, max_length=100)
    start_date: date | None = None
    primary_completion_date: date | None = None
    completion_date: date | None = None
    first_posted: date | None = None
    last_update_posted: date | None = None
    url: str | None = Field(None, max_length=300)

    @model_validator(mode="after")
    def check_dates(self):
        if self.start_date and self.completion_date and self.completion_date < self.start_date:
            raise ValueError("completion_date cannot be before start_date")
        return self


class TrialCreate(TrialFields):
    nct_number: str = Field(pattern=r"^NCT\d{8}$", examples=["NCT04280705"])
    locations: list[LocationBase] = []


class TrialUpdate(BaseModel):
    """Partial update: only the fields sent are changed."""

    model_config = ConfigDict(use_enum_values=True, str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=2000)
    acronym: str | None = Field(None, max_length=100)
    status: TrialStatus | None = None
    has_results: bool | None = None
    conditions: list[str] | None = None
    interventions: list[str] | None = None
    outcome_measures: list[str] | None = None
    sponsors: list[str] | None = None
    funded_by: list[str] | None = None
    study_designs: list[str] | None = None
    gender: Gender | None = None
    age_description: str | None = Field(None, max_length=200)
    phases: str | None = Field(None, max_length=50)
    enrollment: int | None = Field(None, ge=0)
    study_type: str | None = Field(None, max_length=100)
    start_date: date | None = None
    primary_completion_date: date | None = None
    completion_date: date | None = None
    first_posted: date | None = None
    last_update_posted: date | None = None
    url: str | None = Field(None, max_length=300)
    locations: list[LocationBase] | None = None

    @model_validator(mode="after")
    def required_fields_not_null(self):
        for name in ("title", "status", "has_results"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


# --------------------------------------------------------------------------- trials: output


class TrialListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nct_number: str
    title: str
    acronym: str | None
    status: str
    phases: str | None
    study_type: str | None
    gender: str | None
    enrollment: int | None
    start_date: date | None
    has_results: bool
    url: str | None


class TrialDetail(TrialListItem):
    conditions: list[str]
    interventions: list[str]
    outcome_measures: list[str]
    sponsors: list[str]
    funded_by: list[str]
    study_designs: list[str]
    age_description: str | None
    min_age_years: float | None
    max_age_years: float | None
    includes_children: bool
    includes_adults: bool
    includes_older_adults: bool
    primary_completion_date: date | None
    completion_date: date | None
    first_posted: date | None
    last_update_posted: date | None
    locations: list[LocationRead]
    created_at: datetime | None
    updated_at: datetime | None

    @field_validator(*MULTI_VALUE_FIELDS, mode="before")
    @classmethod
    def split_pipe_delimited(cls, value):
        return split_multi(value) if not isinstance(value, list) else value


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


# --------------------------------------------------------------------------- analytics


class CountItem(BaseModel):
    label: str
    count: int
    percentage: float


class Summary(BaseModel):
    total_trials: int
    trials_with_results: int
    percent_with_results: float
    countries: int
    total_enrollment: int
    average_enrollment: float | None
    median_enrollment: float | None
    max_enrollment: int | None
    earliest_start_date: date | None
    latest_start_date: date | None


class TimelinePoint(BaseModel):
    period: str
    count: int


class PhaseEnrollment(BaseModel):
    phase: str
    trials: int
    average_enrollment: float | None
    max_enrollment: int | None


class AgeGroupCounts(BaseModel):
    child: int
    adult: int
    older_adult: int


class EtlRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    rows_read: int
    rows_valid: int
    rows_rejected: int
    inserted: int
    updated: int
    error_message: str | None
