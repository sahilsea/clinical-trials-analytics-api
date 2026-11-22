from datetime import date

import pytest

from app.parsing import (
    clean_text,
    join_multi,
    normalize_phases,
    parse_age,
    parse_date,
    parse_has_results,
    parse_int,
    parse_locations,
    split_multi,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("18 Years and older   (Adult, Older Adult)", (18.0, None, False, True, True)),
        ("18 Years to 80 Years   (Adult, Older Adult)", (18.0, 80.0, False, True, True)),
        ("up to 17 Years   (Child)", (None, 17.0, True, False, False)),
        ("Child, Adult, Older Adult", (None, None, True, True, True)),
        ("6 Months to 17 Years   (Child)", (0.5, 17.0, True, False, False)),
        ("65 Years and older   (Older Adult)", (65.0, None, False, False, True)),
    ],
)
def test_parse_age(text, expected):
    age = parse_age(text)
    assert (
        age.min_years,
        age.max_years,
        age.includes_children,
        age.includes_adults,
        age.includes_older_adults,
    ) == expected


def test_parse_age_handles_missing_value():
    age = parse_age(None)
    assert age.min_years is None and not age.includes_adults


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("March 27, 2020", date(2020, 3, 27)),
        ("March 2020", date(2020, 3, 1)),
        ("2021-06-15", date(2021, 6, 15)),
        ("not a date", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_date(text, expected):
    assert parse_date(text) == expected


def test_parse_locations_with_state_and_without():
    locations = parse_locations(
        "Site 1, Boston, Massachusetts, United States|Hopital A, Paris, France|Lima, Peru|Japan"
    )
    assert locations == [
        {
            "facility": "Site 1",
            "city": "Boston",
            "state": "Massachusetts",
            "country": "United States",
        },
        {"facility": "Hopital A", "city": "Paris", "state": None, "country": "France"},
        {"facility": None, "city": "Lima", "state": None, "country": "Peru"},
        {"facility": None, "city": None, "state": None, "country": "Japan"},
    ]


def test_parse_locations_keeps_commas_inside_facility_name():
    [location] = parse_locations("Dept of Medicine, Big Hospital, Austin, Texas, United States")
    assert location["facility"] == "Dept of Medicine, Big Hospital"
    assert location["city"] == "Austin"


def test_parse_locations_empty():
    assert parse_locations(None) == []
    assert parse_locations("") == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Phase 1|Phase 2", "Phase 1/Phase 2"), ("Phase 3", "Phase 3"), (None, None), ("", None)],
)
def test_normalize_phases(raw, expected):
    assert normalize_phases(raw) == expected


def test_parse_int():
    assert parse_int("120.0") == 120
    assert parse_int("abc") is None
    assert parse_int("-5") is None
    assert parse_int(float("nan")) is None


def test_text_helpers():
    assert clean_text("  hi  ") == "hi"
    assert clean_text("   ") is None
    assert split_multi("a| b ||c") == ["a", "b", "c"]
    assert join_multi(["a", " ", "b"]) == "a|b"
    assert join_multi([]) is None
    assert parse_has_results("Has Results") is True
    assert parse_has_results("No Results Available") is False
