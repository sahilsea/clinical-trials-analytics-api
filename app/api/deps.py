"""Shared FastAPI dependencies: auth, filters and pagination."""

import secrets
from dataclasses import dataclass
from datetime import date

from fastapi import Depends, HTTPException, Query, Security, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings
from app.filters import TrialFilters
from app.schemas import AgeGroup, Gender, TrialStatus

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    api_key: str | None = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """Protect write endpoints. compare_digest avoids leaking the key through timing."""
    if not api_key or not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API-Key"},
        )


def trial_filters(
    q: str | None = Query(None, min_length=2, max_length=100, description="Free-text search"),
    status_: list[TrialStatus] | None = Query(None, alias="status"),
    phase: str | None = Query(None, examples=["Phase 3"]),
    study_type: str | None = Query(None, examples=["Interventional"]),
    gender: Gender | None = None,
    country: str | None = Query(None, examples=["France"]),
    has_results: bool | None = None,
    age_group: AgeGroup | None = None,
    min_enrollment: int | None = Query(None, ge=0),
    max_enrollment: int | None = Query(None, ge=0),
    start_date_from: date | None = None,
    start_date_to: date | None = None,
) -> TrialFilters:
    if None not in (min_enrollment, max_enrollment) and min_enrollment > max_enrollment:
        raise HTTPException(422, "min_enrollment cannot be greater than max_enrollment")
    if start_date_from and start_date_to and start_date_from > start_date_to:
        raise HTTPException(422, "start_date_from cannot be after start_date_to")
    return TrialFilters(
        q=q,
        status=[s.value for s in status_] if status_ else None,
        phase=phase,
        study_type=study_type,
        gender=gender.value if gender else None,
        country=country,
        has_results=has_results,
        age_group=age_group,
        min_enrollment=min_enrollment,
        max_enrollment=max_enrollment,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
    )


@dataclass
class Pagination:
    page: int
    page_size: int


def pagination(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Pagination:
    return Pagination(page=page, page_size=page_size)
