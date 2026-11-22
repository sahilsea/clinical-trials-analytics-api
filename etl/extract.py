"""Extract: read the raw CSV and check it has the columns we depend on."""

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {"NCT Number", "Title", "Status"}


class ExtractError(Exception):
    pass


def extract_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise ExtractError(f"CSV file not found: {path}")

    # Read everything as text; typing and validation happen in the transform step.
    df = pd.read_csv(path, dtype=str, keep_default_na=True)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ExtractError(f"CSV is missing required columns: {sorted(missing)}")

    # Replace pandas' NaN/NA markers with plain None so downstream code sees Python values.
    return df.astype(object).where(df.notna(), None)
