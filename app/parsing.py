"""Domain parsing rules shared by the ETL pipeline and the API.

Keeping these in one place means a trial created through `POST /trials` is
normalised exactly like one loaded from the CSV.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

MULTI_VALUE_DELIMITER = "|"

_UNIT_TO_YEARS = {
    "year": 1.0,
    "month": 1 / 12,
    "week": 1 / 52,
    "day": 1 / 365,
    "hour": 1 / (365 * 24),
    "minute": 1 / (365 * 24 * 60),
}
_AGE_VALUE = re.compile(r"(\d+(?:\.\d+)?)\s*(year|month|week|day|hour|minute)s?", re.IGNORECASE)
_PARENTHESES = re.compile(r"\(([^)]*)\)")
_DATE_FORMATS = ("%B %d, %Y", "%B %Y", "%b %d, %Y", "%b %Y", "%Y-%m-%d", "%Y-%m")


def clean_text(value: Any) -> str | None:
    """Return a stripped string, or None for blanks and pandas NaN."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def split_multi(value: Any) -> list[str]:
    """Split a pipe-delimited field ("COVID-19|Pneumonia") into a list."""
    text = clean_text(value)
    if text is None:
        return []
    return [part.strip() for part in text.split(MULTI_VALUE_DELIMITER) if part.strip()]


def join_multi(values: Iterable[str] | None) -> str | None:
    cleaned = [v.strip() for v in values or [] if v and v.strip()]
    return MULTI_VALUE_DELIMITER.join(cleaned) or None


def parse_int(value: Any) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        number = int(float(text))
    except ValueError:
        return None
    return number if number >= 0 else None


def parse_date(value: Any) -> date | None:
    """Parse ClinicalTrials.gov dates such as "March 27, 2020" or "March 2020"."""
    text = clean_text(value)
    if text is None:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def normalize_phases(value: Any) -> str | None:
    """ "Phase 1|Phase 2" -> "Phase 1/Phase 2"; blanks -> None."""
    return "/".join(split_multi(value)) or None


def parse_has_results(value: Any) -> bool:
    return (clean_text(value) or "").lower() == "has results"


@dataclass(frozen=True)
class AgeInfo:
    min_years: float | None = None
    max_years: float | None = None
    includes_children: bool = False
    includes_adults: bool = False
    includes_older_adults: bool = False


def _to_years(amount: str, unit: str) -> float:
    return round(float(amount) * _UNIT_TO_YEARS[unit.lower()], 2)


def parse_age(value: Any) -> AgeInfo:
    """Parse eligibility text like "18 Years to 80 Years   (Adult, Older Adult)"."""
    text = clean_text(value)
    if text is None:
        return AgeInfo()

    lower = text.lower()
    values = [_to_years(amount, unit) for amount, unit in _AGE_VALUE.findall(text)]
    min_years = max_years = None
    if lower.startswith("up to") and values:
        max_years = values[0]
    elif " to " in lower and len(values) >= 2:
        min_years, max_years = values[0], values[1]
    elif "and older" in lower and values:
        min_years = values[0]

    # Age groups come from the parenthetical "(Child, Adult)", or the whole text when
    # the field is only a group list such as "Child, Adult, Older Adult".
    match = _PARENTHESES.search(text)
    groups = (match.group(1) if match else text).lower()
    return AgeInfo(
        min_years=min_years,
        max_years=max_years,
        includes_children="child" in groups,
        includes_adults="adult" in groups.replace("older adult", ""),
        includes_older_adults="older adult" in groups,
    )


def parse_locations(value: Any) -> list[dict[str, str | None]]:
    """Parse "Facility, City, State, Country|..." into structured locations.

    The country is always the last comma-separated part. With four or more parts
    the two before it are city and state; with three, it is facility and city.
    """
    locations: list[dict[str, str | None]] = []
    for entry in split_multi(value):
        parts = [p.strip() for p in entry.split(",") if p.strip()]
        if not parts:
            continue
        facility = city = state = None
        if len(parts) >= 4:
            facility, city, state = ", ".join(parts[:-3]), parts[-3], parts[-2]
        elif len(parts) == 3:
            facility, city = parts[0], parts[1]
        elif len(parts) == 2:
            city = parts[0]
        locations.append({"facility": facility, "city": city, "state": state, "country": parts[-1]})
    return locations
