"""Run the full ETL pipeline.

python -m etl.pipeline data/COVID_clinical_trials.csv
python -m etl.pipeline data/COVID_clinical_trials.csv --dry-run --rejects rejects.csv
"""

import argparse
import csv
import logging
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import EtlRun
from etl.extract import extract_csv
from etl.load import load
from etl.transform import RejectedRow, transform

logger = logging.getLogger("etl")


@dataclass
class PipelineResult:
    rows_read: int
    rows_valid: int
    rows_rejected: int
    duplicates_dropped: int
    inserted: int
    updated: int
    seconds: float
    rejected: list[RejectedRow]


def run_pipeline(db: Session, csv_path: str | Path, *, dry_run: bool = False) -> PipelineResult:
    started = time.perf_counter()
    run = EtlRun(source=str(csv_path), status="running", started_at=datetime.now(UTC))
    if not dry_run:
        db.add(run)
        db.commit()

    try:
        df = extract_csv(csv_path)
        logger.info("Extracted %d rows from %s", len(df), csv_path)

        transformed = transform(df)
        logger.info(
            "Transformed: %d valid, %d rejected, %d duplicates dropped",
            len(transformed.records),
            len(transformed.rejected),
            transformed.duplicates_dropped,
        )

        inserted = updated = 0
        if not dry_run:
            loaded = load(db, transformed.records)
            inserted, updated = loaded.inserted, loaded.updated
            logger.info("Loaded: %d inserted, %d updated", inserted, updated)
    except Exception as exc:
        if not dry_run:
            run.status, run.error_message = "failed", str(exc)
            run.finished_at = datetime.now(UTC)
            db.commit()
        raise

    result = PipelineResult(
        rows_read=len(df),
        rows_valid=len(transformed.records),
        rows_rejected=len(transformed.rejected),
        duplicates_dropped=transformed.duplicates_dropped,
        inserted=inserted,
        updated=updated,
        seconds=round(time.perf_counter() - started, 2),
        rejected=transformed.rejected,
    )
    if not dry_run:
        run.status = "success"
        run.finished_at = datetime.now(UTC)
        run.rows_read, run.rows_valid = result.rows_read, result.rows_valid
        run.rows_rejected = result.rows_rejected
        run.inserted, run.updated = inserted, updated
        db.commit()
    return result


def write_rejects(rejected: list[RejectedRow], path: Path) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["row_number", "nct_number", "reason"])
        writer.writeheader()
        writer.writerows(asdict(r) for r in rejected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load a ClinicalTrials.gov CSV export.")
    parser.add_argument("csv_path", type=Path, help="Path to the CSV export")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, write nothing")
    parser.add_argument("--rejects", type=Path, help="Write rejected rows to this CSV")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db()
    with SessionLocal() as db:
        try:
            result = run_pipeline(db, args.csv_path, dry_run=args.dry_run)
        except Exception as exc:
            logger.error("Pipeline failed: %s", exc)
            return 1

    if args.rejects and result.rejected:
        write_rejects(result.rejected, args.rejects)
        logger.info("Wrote %d rejected rows to %s", len(result.rejected), args.rejects)
    for rejected in result.rejected[:5]:
        logger.warning("Rejected row %d (%s): %s", *asdict(rejected).values())

    print(
        f"\nETL {'dry run ' if args.dry_run else ''}complete in {result.seconds}s: "
        f"{result.rows_read} read, {result.rows_valid} valid, {result.rows_rejected} rejected, "
        f"{result.inserted} inserted, {result.updated} updated"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
