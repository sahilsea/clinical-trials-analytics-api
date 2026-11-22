"""Reusable query filters, shared by the trials list and the analytics endpoints."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, or_

from app.models import Trial, TrialLocation
from app.schemas import AgeGroup


@dataclass
class TrialFilters:
    q: str | None = None
    status: list[str] | None = None
    phase: str | None = None
    study_type: str | None = None
    gender: str | None = None
    country: str | None = None
    has_results: bool | None = None
    age_group: AgeGroup | None = None
    min_enrollment: int | None = None
    max_enrollment: int | None = None
    start_date_from: date | None = None
    start_date_to: date | None = None

    def apply(self, stmt: Select) -> Select:
        """Add WHERE clauses for every filter that is set. `stmt` must involve `Trial`."""
        if self.q:
            pattern = f"%{self.q.strip()}%"
            stmt = stmt.where(
                or_(
                    Trial.title.ilike(pattern),
                    Trial.acronym.ilike(pattern),
                    Trial.conditions.ilike(pattern),
                    Trial.interventions.ilike(pattern),
                    Trial.nct_number.ilike(pattern),
                )
            )
        if self.status:
            stmt = stmt.where(Trial.status.in_(self.status))
        if self.phase:
            stmt = stmt.where(Trial.phases == self.phase)
        if self.study_type:
            stmt = stmt.where(Trial.study_type == self.study_type)
        if self.gender:
            stmt = stmt.where(Trial.gender == self.gender)
        if self.country:
            stmt = stmt.where(Trial.locations.any(TrialLocation.country.ilike(self.country)))
        if self.has_results is not None:
            stmt = stmt.where(Trial.has_results.is_(self.has_results))
        if self.age_group:
            column = {
                AgeGroup.CHILD: Trial.includes_children,
                AgeGroup.ADULT: Trial.includes_adults,
                AgeGroup.OLDER_ADULT: Trial.includes_older_adults,
            }[self.age_group]
            stmt = stmt.where(column.is_(True))
        if self.min_enrollment is not None:
            stmt = stmt.where(Trial.enrollment >= self.min_enrollment)
        if self.max_enrollment is not None:
            stmt = stmt.where(Trial.enrollment <= self.max_enrollment)
        if self.start_date_from:
            stmt = stmt.where(Trial.start_date >= self.start_date_from)
        if self.start_date_to:
            stmt = stmt.where(Trial.start_date <= self.start_date_to)
        return stmt
