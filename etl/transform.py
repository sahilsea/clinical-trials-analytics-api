"""Transform: clean raw CSV rows and validate them against the API's TrialCreate schema.

This is the production version of the cleaning done in the EDA notebook. One
deliberate difference: the notebook imputed missing enrollment with the median,
which is fine for charts but wrong for a system of record, so NULLs stay NULL here.
"""

from dataclasses import dataclass, field

import pandas as pd
from pydantic import ValidationError

from app.parsing import (
    clean_text,
    normalize_phases,
    parse_date,
    parse_has_results,
    parse_int,
    parse_locations,
    split_multi,
)
from app.schemas import TrialCreate


@dataclass
class RejectedRow:
    row_number: int  # 1-based line in the CSV, header excluded
    nct_number: str | None
    reason: str


@dataclass
class TransformResult:
    records: list[TrialCreate] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)
    duplicates_dropped: int = 0


def row_to_payload(row: dict) -> dict:
    """Map one raw CSV row (ClinicalTrials.gov column names) to TrialCreate fields."""
    nct = clean_text(row.get("NCT Number"))
    return {
        "nct_number": nct.upper() if nct else nct,
        "title": clean_text(row.get("Title")),
        "acronym": clean_text(row.get("Acronym")),
        "status": clean_text(row.get("Status")),
        "has_results": parse_has_results(row.get("Study Results")),
        "conditions": split_multi(row.get("Conditions")),
        "interventions": split_multi(row.get("Interventions")),
        "outcome_measures": split_multi(row.get("Outcome Measures")),
        "sponsors": split_multi(row.get("Sponsor/Collaborators")),
        "funded_by": split_multi(row.get("Funded Bys")),
        "study_designs": split_multi(row.get("Study Designs")),
        "gender": clean_text(row.get("Gender")),
        "age_description": clean_text(row.get("Age")),
        "phases": normalize_phases(row.get("Phases")),
        "enrollment": parse_int(row.get("Enrollment")),
        "study_type": clean_text(row.get("Study Type")),
        "start_date": parse_date(row.get("Start Date")),
        "primary_completion_date": parse_date(row.get("Primary Completion Date")),
        "completion_date": parse_date(row.get("Completion Date")),
        "first_posted": parse_date(row.get("First Posted")),
        "last_update_posted": parse_date(row.get("Last Update Posted")),
        "url": clean_text(row.get("URL")),
        "locations": parse_locations(row.get("Locations")),
    }


def _describe(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in e['loc']) or 'row'}: {e['msg']}" for e in error.errors()
    )


def transform(df: pd.DataFrame) -> TransformResult:
    result = TransformResult()

    # A trial can appear twice in an export; the last occurrence wins.
    before = len(df)
    df = df.drop_duplicates(subset="NCT Number", keep="last")
    result.duplicates_dropped = before - len(df)

    for index, row in zip(df.index, df.to_dict("records"), strict=True):
        payload = row_to_payload(row)
        try:
            result.records.append(TrialCreate(**payload))
        except ValidationError as exc:
            result.rejected.append(
                RejectedRow(int(index) + 1, payload.get("nct_number"), _describe(exc))
            )
    return result
