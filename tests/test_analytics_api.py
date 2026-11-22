def test_summary(client):
    body = client.get("/api/v1/analytics/summary").json()
    assert body == {
        "total_trials": 11,
        "trials_with_results": 2,
        "percent_with_results": 18.18,
        "countries": 8,
        "total_enrollment": 2875,
        "average_enrollment": 319.4,
        "median_enrollment": 120.0,
        "max_enrollment": 1500,
        "earliest_start_date": "2020-03-15",
        "latest_start_date": "2021-02-01",
    }


def test_summary_respects_filters(client):
    body = client.get("/api/v1/analytics/summary", params={"country": "Spain"}).json()
    assert body["total_trials"] == 1
    assert body["trials_with_results"] == 1


def test_summary_on_empty_result(client):
    body = client.get("/api/v1/analytics/summary", params={"q": "zzzz-nothing"}).json()
    assert body["total_trials"] == 0
    assert body["median_enrollment"] is None
    assert body["percent_with_results"] == 0.0


def test_status_distribution(client):
    items = client.get("/api/v1/analytics/distribution/status").json()
    assert items[0] == {"label": "Recruiting", "count": 3, "percentage": 27.27}
    assert sum(i["count"] for i in items) == 11


def test_phase_distribution_labels_missing_as_unknown(client):
    counts = {
        i["label"]: i["count"] for i in client.get("/api/v1/analytics/distribution/phase").json()
    }
    assert counts["Not Applicable"] == 3
    assert counts["Unknown"] == 2
    assert counts["Phase 1/Phase 2"] == 1


def test_unknown_distribution_field_returns_422(client):
    assert client.get("/api/v1/analytics/distribution/sponsor").status_code == 422


def test_top_countries(client):
    items = client.get("/api/v1/analytics/countries", params={"limit": 3}).json()
    assert len(items) == 3
    assert items[0] == {"label": "United States", "count": 2, "percentage": 18.18}


def test_timeline_by_year(client):
    points = client.get("/api/v1/analytics/timeline", params={"granularity": "year"}).json()
    assert points == [{"period": "2020", "count": 8}, {"period": "2021", "count": 2}]


def test_timeline_by_month(client):
    points = client.get("/api/v1/analytics/timeline").json()
    assert {"period": "2020-04", "count": 2} in points
    assert [p["period"] for p in points] == sorted(p["period"] for p in points)


def test_age_groups(client):
    body = client.get("/api/v1/analytics/age-groups").json()
    assert body == {"child": 2, "adult": 9, "older_adult": 7}


def test_enrollment_by_phase(client):
    rows = {r["phase"]: r for r in client.get("/api/v1/analytics/enrollment-by-phase").json()}
    assert rows["Phase 3"] == {
        "phase": "Phase 3",
        "trials": 2,
        "average_enrollment": 300.0,
        "max_enrollment": 600,
    }
