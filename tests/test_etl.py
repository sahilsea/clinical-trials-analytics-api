import pandas as pd
import pytest
from sqlalchemy import func, select

from app.models import EtlRun, Trial, TrialLocation
from etl.extract import ExtractError, extract_csv
from etl.pipeline import main, run_pipeline
from etl.transform import transform
from tests.conftest import FIXTURE_CSV


def test_extract_rejects_missing_file(tmp_path):
    with pytest.raises(ExtractError, match="not found"):
        extract_csv(tmp_path / "nope.csv")


def test_extract_rejects_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Title,Status\nA,Recruiting\n")
    with pytest.raises(ExtractError, match="NCT Number"):
        extract_csv(path)


def test_transform_validates_rows():
    result = transform(extract_csv(FIXTURE_CSV))
    assert len(result.records) == 11
    [rejected] = result.rejected
    assert rejected.nct_number == "INVALID-1"
    assert "nct_number" in rejected.reason


def test_transform_drops_duplicates_keeping_last():
    df = pd.DataFrame(
        [
            {"NCT Number": "NCT00000001", "Title": "Old title", "Status": "Recruiting"},
            {"NCT Number": "NCT00000001", "Title": "New title", "Status": "Completed"},
        ]
    )
    result = transform(df)
    assert result.duplicates_dropped == 1
    assert [r.title for r in result.records] == ["New title"]


def test_transform_rejects_unknown_status():
    df = pd.DataFrame([{"NCT Number": "NCT00000001", "Title": "T", "Status": "Paused"}])
    result = transform(df)
    assert result.records == []
    assert "status" in result.rejected[0].reason


def test_pipeline_loads_and_is_idempotent(db):
    first = run_pipeline(db, FIXTURE_CSV)
    assert (first.inserted, first.updated, first.rows_rejected) == (11, 0, 1)

    second = run_pipeline(db, FIXTURE_CSV)
    assert (second.inserted, second.updated) == (0, 11)

    assert db.scalar(select(func.count(Trial.id))) == 11
    # Locations are replaced on update, not duplicated: 12 parsed locations in the fixture.
    assert db.scalar(select(func.count(TrialLocation.id))) == 12


def test_pipeline_records_etl_runs(db):
    run_pipeline(db, FIXTURE_CSV)
    run = db.scalar(select(EtlRun))
    assert run.status == "success"
    assert (run.rows_read, run.rows_valid, run.rows_rejected) == (12, 11, 1)


def test_pipeline_records_failed_run(db, tmp_path):
    with pytest.raises(ExtractError):
        run_pipeline(db, tmp_path / "missing.csv")
    run = db.scalar(select(EtlRun))
    assert run.status == "failed"
    assert "not found" in run.error_message


def test_dry_run_writes_nothing(db):
    result = run_pipeline(db, FIXTURE_CSV, dry_run=True)
    assert result.rows_valid == 11
    assert db.scalar(select(func.count(Trial.id))) == 0
    assert db.scalar(select(func.count(EtlRun.id))) == 0


def test_cli_writes_reject_report(db, tmp_path, capsys):
    rejects = tmp_path / "rejects.csv"
    assert main([str(FIXTURE_CSV), "--dry-run", "--rejects", str(rejects)]) == 0
    assert "INVALID-1" in rejects.read_text()
    assert "11 valid" in capsys.readouterr().out


def test_transform_accepts_long_real_world_values():
    """Regression: values found in the real export that exceeded the first length limits."""
    long_city = "Department of Infectious Diseases and Tropical Medicine " * 3
    df = pd.DataFrame(
        [
            {
                "NCT Number": "NCT00000002",
                "Title": "T",
                "Status": "Available",
                "Study Type": "Expanded Access:Individual Patients|Intermediate-size Population",
                "Locations": f"Hospital, {long_city.strip()}, Some State, Italy",
            }
        ]
    )
    result = transform(df)
    assert result.rejected == []
    assert result.records[0].locations[0].country == "Italy"
