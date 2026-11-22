"""Data-access layer for trials. Routes call these functions instead of writing SQL."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.filters import TrialFilters
from app.models import Trial, TrialLocation
from app.parsing import join_multi, parse_age
from app.schemas import (
    MULTI_VALUE_FIELDS,
    LocationBase,
    SortField,
    SortOrder,
    TrialCreate,
    TrialUpdate,
)


class TrialAlreadyExistsError(Exception):
    pass


def to_columns(data: dict[str, Any]) -> dict[str, Any]:
    """Turn API/ETL input into column values, deriving the computed fields."""
    columns = {key: value for key, value in data.items() if key != "locations"}
    for field in MULTI_VALUE_FIELDS:
        if field in columns:
            columns[field] = join_multi(columns[field])
    if "age_description" in columns:
        age = parse_age(columns["age_description"])
        columns.update(
            min_age_years=age.min_years,
            max_age_years=age.max_years,
            includes_children=age.includes_children,
            includes_adults=age.includes_adults,
            includes_older_adults=age.includes_older_adults,
        )
    return columns


def build_locations(locations: list[LocationBase] | list[dict]) -> list[TrialLocation]:
    return [
        TrialLocation(**(loc.model_dump() if isinstance(loc, LocationBase) else loc))
        for loc in locations
    ]


def list_trials(
    db: Session,
    filters: TrialFilters,
    *,
    sort_by: SortField = SortField.START_DATE,
    order: SortOrder = SortOrder.DESC,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Trial], int]:
    stmt = filters.apply(select(Trial))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    column = getattr(Trial, sort_by.value)
    ordering = column.asc() if order == SortOrder.ASC else column.desc()
    stmt = (
        stmt.order_by(ordering.nulls_last(), Trial.id)  # id makes pagination deterministic
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt)), total


def get_trial(db: Session, nct_number: str) -> Trial | None:
    return db.scalar(select(Trial).where(Trial.nct_number == nct_number.upper()))


def create_trial(db: Session, payload: TrialCreate) -> Trial:
    if get_trial(db, payload.nct_number):
        raise TrialAlreadyExistsError(payload.nct_number)
    trial = Trial(**to_columns(payload.model_dump()), locations=build_locations(payload.locations))
    db.add(trial)
    db.commit()
    db.refresh(trial)
    return trial


def update_trial(db: Session, trial: Trial, payload: TrialUpdate) -> Trial:
    changes = payload.model_dump(exclude_unset=True)
    for key, value in to_columns(changes).items():
        setattr(trial, key, value)
    if "locations" in changes:
        trial.locations = build_locations(payload.locations or [])
    db.commit()
    db.refresh(trial)
    return trial


def delete_trial(db: Session, trial: Trial) -> None:
    db.delete(trial)
    db.commit()
