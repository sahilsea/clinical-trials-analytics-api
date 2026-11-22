"""Analytics endpoints. Every endpoint accepts the same filters as GET /trials."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import trial_filters
from app.database import get_db
from app.filters import TrialFilters
from app.schemas import AgeGroupCounts, CountItem, PhaseEnrollment, Summary, TimelinePoint
from app.services import analytics
from app.services.analytics import DateField, DistributionField, Granularity

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=Summary)
def summary(filters: TrialFilters = Depends(trial_filters), db: Session = Depends(get_db)):
    return analytics.summary(db, filters)


@router.get(
    "/distribution/{field}",
    response_model=list[CountItem],
    summary="Count trials by status, phase, study type or gender",
)
def distribution(
    field: DistributionField,
    filters: TrialFilters = Depends(trial_filters),
    db: Session = Depends(get_db),
):
    return analytics.distribution(db, field, filters)


@router.get("/countries", response_model=list[CountItem], summary="Countries with most trials")
def countries(
    limit: int = Query(10, ge=1, le=100),
    filters: TrialFilters = Depends(trial_filters),
    db: Session = Depends(get_db),
):
    return analytics.top_countries(db, filters, limit)


@router.get("/timeline", response_model=list[TimelinePoint], summary="Trials per month or year")
def timeline(
    granularity: Granularity = Granularity.MONTH,
    date_field: DateField = DateField.START_DATE,
    filters: TrialFilters = Depends(trial_filters),
    db: Session = Depends(get_db),
):
    return analytics.timeline(db, filters, granularity, date_field)


@router.get("/age-groups", response_model=AgeGroupCounts)
def age_groups(filters: TrialFilters = Depends(trial_filters), db: Session = Depends(get_db)):
    return analytics.age_groups(db, filters)


@router.get("/enrollment-by-phase", response_model=list[PhaseEnrollment])
def enrollment_by_phase(
    filters: TrialFilters = Depends(trial_filters), db: Session = Depends(get_db)
):
    return analytics.enrollment_by_phase(db, filters)
