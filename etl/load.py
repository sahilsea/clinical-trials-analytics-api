"""Load: upsert validated trials into the database in batches.

Re-running the pipeline on the same file is safe (idempotent): existing trials
are updated in place, new ones are inserted, nothing is duplicated.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Trial
from app.repository import build_locations, to_columns
from app.schemas import TrialCreate


@dataclass
class LoadResult:
    inserted: int = 0
    updated: int = 0


def _batches(items: Sequence[TrialCreate], size: int) -> Iterator[Sequence[TrialCreate]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def load(db: Session, records: Sequence[TrialCreate], batch_size: int = 500) -> LoadResult:
    """Upsert all records in one transaction: either everything loads or nothing does."""
    result = LoadResult()
    try:
        for batch in _batches(records, batch_size):
            ncts = [r.nct_number for r in batch]
            existing = {
                t.nct_number: t for t in db.scalars(select(Trial).where(Trial.nct_number.in_(ncts)))
            }
            for record in batch:
                columns = to_columns(record.model_dump())
                locations = build_locations(record.locations)
                trial = existing.get(record.nct_number)
                if trial is None:
                    db.add(Trial(**columns, locations=locations))
                    result.inserted += 1
                else:
                    for key, value in columns.items():
                        setattr(trial, key, value)
                    trial.locations = locations
                    result.updated += 1
            db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result
