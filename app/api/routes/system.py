"""Operational endpoints: health check and ETL run history."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.database import get_db
from app.models import EtlRun
from app.schemas import EtlRunRead

router = APIRouter(tags=["System"])


@router.get("/health", summary="Liveness and database connectivity")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    except SQLAlchemyError:
        database_ok = False
    return JSONResponse(
        status_code=200 if database_ok else 503,
        content={
            "status": "ok" if database_ok else "degraded",
            "database": "ok" if database_ok else "unreachable",
            "version": __version__,
        },
    )


@router.get("/api/v1/etl-runs", response_model=list[EtlRunRead], summary="Recent ETL runs")
def etl_runs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return db.scalars(select(EtlRun).order_by(EtlRun.id.desc()).limit(limit)).all()
