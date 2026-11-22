import math

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.orm import Session

from app import repository
from app.api.deps import Pagination, pagination, require_api_key, trial_filters
from app.database import get_db
from app.filters import TrialFilters
from app.models import Trial
from app.schemas import (
    Page,
    SortField,
    SortOrder,
    TrialCreate,
    TrialDetail,
    TrialListItem,
    TrialUpdate,
)

router = APIRouter(prefix="/trials", tags=["Trials"])

NctNumber = Path(pattern=r"^[Nn][Cc][Tt]\d{8}$", examples=["NCT04280705"])


def get_trial_or_404(nct_number: str = NctNumber, db: Session = Depends(get_db)) -> Trial:
    trial = repository.get_trial(db, nct_number)
    if trial is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Trial {nct_number.upper()} not found")
    return trial


@router.get("", response_model=Page[TrialListItem], summary="Search and filter trials")
def list_trials(
    filters: TrialFilters = Depends(trial_filters),
    paging: Pagination = Depends(pagination),
    sort_by: SortField = SortField.START_DATE,
    order: SortOrder = SortOrder.DESC,
    db: Session = Depends(get_db),
):
    items, total = repository.list_trials(
        db, filters, sort_by=sort_by, order=order, page=paging.page, page_size=paging.page_size
    )
    return Page(
        items=items,
        total=total,
        page=paging.page,
        page_size=paging.page_size,
        pages=math.ceil(total / paging.page_size) if total else 0,
    )


@router.get("/{nct_number}", response_model=TrialDetail, summary="Get one trial")
def get_trial(trial: Trial = Depends(get_trial_or_404)):
    return trial


@router.post(
    "",
    response_model=TrialDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
    summary="Create a trial (requires API key)",
)
def create_trial(payload: TrialCreate, response: Response, db: Session = Depends(get_db)):
    try:
        trial = repository.create_trial(db, payload)
    except repository.TrialAlreadyExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Trial {exc} already exists") from exc
    response.headers["Location"] = f"/api/v1/trials/{trial.nct_number}"
    return trial


@router.patch(
    "/{nct_number}",
    response_model=TrialDetail,
    dependencies=[Depends(require_api_key)],
    summary="Partially update a trial (requires API key)",
)
def update_trial(
    payload: TrialUpdate,
    trial: Trial = Depends(get_trial_or_404),
    db: Session = Depends(get_db),
):
    return repository.update_trial(db, trial, payload)


@router.delete(
    "/{nct_number}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
    summary="Delete a trial (requires API key)",
)
def delete_trial(trial: Trial = Depends(get_trial_or_404), db: Session = Depends(get_db)):
    repository.delete_trial(db, trial)
