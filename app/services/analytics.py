"""Aggregation queries behind the /analytics endpoints.

Aggregations run in the database (GROUP BY, COUNT, AVG) rather than loading
rows into Python, so they stay fast as the table grows.
"""

import statistics
from enum import StrEnum

from sqlalchemy import Integer, case, cast, distinct, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.filters import TrialFilters
from app.models import Trial, TrialLocation
from app.schemas import (
    AgeGroupCounts,
    CountItem,
    PhaseEnrollment,
    Summary,
    TimelinePoint,
)

UNKNOWN = "Unknown"


class DistributionField(StrEnum):
    STATUS = "status"
    PHASE = "phase"
    STUDY_TYPE = "study_type"
    GENDER = "gender"


class Granularity(StrEnum):
    MONTH = "month"
    YEAR = "year"


class DateField(StrEnum):
    START_DATE = "start_date"
    FIRST_POSTED = "first_posted"
    COMPLETION_DATE = "completion_date"


_DISTRIBUTION_COLUMNS = {
    DistributionField.STATUS: Trial.status,
    DistributionField.PHASE: Trial.phases,
    DistributionField.STUDY_TYPE: Trial.study_type,
    DistributionField.GENDER: Trial.gender,
}


def _percent(part: int, whole: int) -> float:
    return round(part * 100 / whole, 2) if whole else 0.0


def summary(db: Session, filters: TrialFilters) -> Summary:
    trials = filters.apply(select(Trial.id)).subquery()
    row = db.execute(
        select(
            func.count(Trial.id),
            func.sum(case((Trial.has_results.is_(True), 1), else_=0)),
            func.sum(Trial.enrollment),
            func.avg(Trial.enrollment),
            func.max(Trial.enrollment),
            func.min(Trial.start_date),
            func.max(Trial.start_date),
        ).where(Trial.id.in_(select(trials.c.id)))
    ).one()
    total, with_results, enrollment_sum, enrollment_avg, enrollment_max, first, last = row

    countries = db.scalar(
        select(func.count(distinct(TrialLocation.country))).where(
            TrialLocation.trial_id.in_(select(trials.c.id))
        )
    )
    # Median isn't portable SQL (Postgres has percentile_cont, SQLite has nothing),
    # so fetch only the single enrollment column and compute it here.
    enrollments = db.scalars(
        select(Trial.enrollment).where(
            Trial.id.in_(select(trials.c.id)), Trial.enrollment.is_not(None)
        )
    ).all()

    return Summary(
        total_trials=total,
        trials_with_results=with_results or 0,
        percent_with_results=_percent(with_results or 0, total),
        countries=countries or 0,
        total_enrollment=enrollment_sum or 0,
        average_enrollment=round(float(enrollment_avg), 1) if enrollment_avg is not None else None,
        median_enrollment=float(statistics.median(enrollments)) if enrollments else None,
        max_enrollment=enrollment_max,
        earliest_start_date=first,
        latest_start_date=last,
    )


def distribution(db: Session, field: DistributionField, filters: TrialFilters) -> list[CountItem]:
    column = _DISTRIBUTION_COLUMNS[field]
    label = func.coalesce(column, UNKNOWN).label("label")
    stmt = filters.apply(select(label, func.count(Trial.id).label("n"))).group_by(label)
    rows = db.execute(stmt.order_by(func.count(Trial.id).desc(), label)).all()
    total = sum(n for _, n in rows)
    return [CountItem(label=lbl, count=n, percentage=_percent(n, total)) for lbl, n in rows]


def top_countries(db: Session, filters: TrialFilters, limit: int) -> list[CountItem]:
    total = db.scalar(select(func.count()).select_from(filters.apply(select(Trial.id)).subquery()))
    n_trials = func.count(distinct(TrialLocation.trial_id))
    stmt = filters.apply(
        select(TrialLocation.country, n_trials).join(Trial, TrialLocation.trial_id == Trial.id)
    )
    rows = db.execute(
        stmt.group_by(TrialLocation.country)
        .order_by(n_trials.desc(), TrialLocation.country)
        .limit(limit)
    ).all()
    return [
        CountItem(label=country, count=n, percentage=_percent(n, total or 0)) for country, n in rows
    ]


def _period(column: ColumnElement, granularity: Granularity, dialect: str) -> ColumnElement:
    """Truncate a date to 'YYYY' or 'YYYY-MM' using the right function per database."""
    if dialect == "postgresql":
        return func.to_char(column, "YYYY-MM" if granularity == Granularity.MONTH else "YYYY")
    return func.strftime("%Y-%m" if granularity == Granularity.MONTH else "%Y", column)


def timeline(
    db: Session, filters: TrialFilters, granularity: Granularity, date_field: DateField
) -> list[TimelinePoint]:
    column = getattr(Trial, date_field.value)
    period = _period(column, granularity, db.get_bind().dialect.name).label("period")
    stmt = filters.apply(select(period, func.count(Trial.id))).where(column.is_not(None))
    rows = db.execute(stmt.group_by(period).order_by(period)).all()
    return [TimelinePoint(period=p, count=n) for p, n in rows]


def age_groups(db: Session, filters: TrialFilters) -> AgeGroupCounts:
    def count_true(column):
        return func.coalesce(func.sum(cast(column, Integer)), 0)

    stmt = filters.apply(
        select(
            count_true(Trial.includes_children),
            count_true(Trial.includes_adults),
            count_true(Trial.includes_older_adults),
        )
    )
    child, adult, older = db.execute(stmt).one()
    return AgeGroupCounts(child=child, adult=adult, older_adult=older)


def enrollment_by_phase(db: Session, filters: TrialFilters) -> list[PhaseEnrollment]:
    label = func.coalesce(Trial.phases, UNKNOWN).label("phase")
    stmt = filters.apply(
        select(label, func.count(Trial.id), func.avg(Trial.enrollment), func.max(Trial.enrollment))
    ).group_by(label)
    rows = db.execute(stmt.order_by(label)).all()
    return [
        PhaseEnrollment(
            phase=phase,
            trials=n,
            average_enrollment=round(float(avg), 1) if avg is not None else None,
            max_enrollment=mx,
        )
        for phase, n, avg, mx in rows
    ]
