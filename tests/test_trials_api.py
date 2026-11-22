import pytest

NEW_TRIAL = {
    "nct_number": "NCT99999999",
    "title": "Inhaled Interferon for Mild COVID-19",
    "status": "Recruiting",
    "conditions": ["COVID-19"],
    "interventions": ["Drug: Interferon"],
    "gender": "All",
    "age_description": "18 Years to 60 Years   (Adult)",
    "phases": "Phase 2",
    "enrollment": 250,
    "study_type": "Interventional",
    "start_date": "2021-03-01",
    "locations": [{"facility": "General Hospital", "city": "Oslo", "country": "Norway"}],
}


def nct_numbers(response):
    return [item["nct_number"] for item in response.json()["items"]]


# --------------------------------------------------------------------------- reading


def test_list_trials_paginates(client):
    response = client.get("/api/v1/trials", params={"page_size": 4, "page": 2})
    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["page"], body["page_size"], body["pages"]) == (11, 2, 4, 3)
    assert len(body["items"]) == 4


def test_default_sort_is_newest_start_date_first_with_nulls_last(client):
    items = client.get("/api/v1/trials", params={"page_size": 100}).json()["items"]
    assert items[0]["nct_number"] == "NCT90000008"  # Feb 2021
    assert items[-1]["start_date"] is None


def test_sort_by_enrollment_ascending(client):
    response = client.get("/api/v1/trials", params={"sort_by": "enrollment", "order": "asc"})
    enrollments = [i["enrollment"] for i in response.json()["items"] if i["enrollment"] is not None]
    assert enrollments == sorted(enrollments)


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"q": "plasma"}, {"NCT90000004"}),
        ({"q": "vaccine"}, {"NCT90000002"}),
        ({"status": ["Completed", "Terminated"]}, {"NCT90000002", "NCT90000004", "NCT90000009"}),
        ({"phase": "Phase 3"}, {"NCT90000001", "NCT90000007"}),
        ({"country": "united states"}, {"NCT90000002", "NCT90000005"}),
        ({"gender": "Female"}, {"NCT90000005"}),
        ({"has_results": True}, {"NCT90000002", "NCT90000009"}),
        ({"age_group": "child"}, {"NCT90000003", "NCT90000010"}),
        ({"min_enrollment": 300}, {"NCT90000001", "NCT90000003", "NCT90000006"}),
        ({"study_type": "Observational"}, {"NCT90000003"}),
        (
            {"start_date_from": "2021-01-01"},
            {"NCT90000005", "NCT90000008"},
        ),
        ({"status": ["Recruiting"], "country": "Egypt"}, {"NCT90000012"}),
    ],
)
def test_filters(client, params, expected):
    response = client.get("/api/v1/trials", params={**params, "page_size": 100})
    assert response.status_code == 200
    assert set(nct_numbers(response)) == expected


def test_get_trial_detail(client):
    response = client.get("/api/v1/trials/nct90000001")  # case-insensitive
    assert response.status_code == 200
    trial = response.json()
    assert trial["conditions"] == ["COVID-19", "Pneumonia"]
    assert trial["min_age_years"] == 18.0
    assert trial["includes_older_adults"] is True
    assert {loc["city"] for loc in trial["locations"]} == {"Paris", "Lyon"}


def test_get_missing_trial_returns_404(client):
    response = client.get("/api/v1/trials/NCT12345678")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.parametrize(
    "params",
    [
        {"page_size": 1000},
        {"page": 0},
        {"status": "Paused"},
        {"min_enrollment": 500, "max_enrollment": 10},
        {"start_date_from": "2021-01-01", "start_date_to": "2020-01-01"},
        {"sort_by": "title"},
    ],
)
def test_invalid_query_params_return_422(client, params):
    assert client.get("/api/v1/trials", params=params).status_code == 422


def test_malformed_nct_number_returns_422(client):
    assert client.get("/api/v1/trials/not-an-id").status_code == 422


# --------------------------------------------------------------------------- writing


def test_write_endpoints_require_api_key(client):
    assert client.post("/api/v1/trials", json=NEW_TRIAL).status_code == 401
    bad_key = {"X-API-Key": "wrong"}
    assert client.patch("/api/v1/trials/NCT90000001", json={}, headers=bad_key).status_code == 401
    assert client.delete("/api/v1/trials/NCT90000001", headers=bad_key).status_code == 401


def test_create_trial(client, auth):
    response = client.post("/api/v1/trials", json=NEW_TRIAL, headers=auth)
    assert response.status_code == 201
    assert response.headers["Location"] == "/api/v1/trials/NCT99999999"
    body = response.json()
    assert body["max_age_years"] == 60.0  # derived from age_description
    assert body["locations"][0]["country"] == "Norway"
    assert client.get("/api/v1/trials/NCT99999999").status_code == 200


def test_create_duplicate_returns_409(client, auth):
    payload = {**NEW_TRIAL, "nct_number": "NCT90000001"}
    assert client.post("/api/v1/trials", json=payload, headers=auth).status_code == 409


@pytest.mark.parametrize(
    "override",
    [
        {"nct_number": "12345"},
        {"status": "Paused"},
        {"enrollment": -1},
        {"title": ""},
        {"start_date": "2021-05-01", "completion_date": "2020-01-01"},
    ],
)
def test_create_validation_errors(client, auth, override):
    response = client.post("/api/v1/trials", json={**NEW_TRIAL, **override}, headers=auth)
    assert response.status_code == 422


def test_patch_updates_only_sent_fields(client, auth):
    response = client.patch(
        "/api/v1/trials/NCT90000001",
        json={"status": "Completed", "age_description": "up to 17 Years   (Child)"},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Completed"
    assert body["includes_children"] is True and body["includes_adults"] is False
    assert body["title"] == "Antiviral Drug A in Hospitalized COVID-19 Patients"  # untouched
    assert len(body["locations"]) == 2  # untouched


def test_patch_replaces_locations(client, auth):
    response = client.patch(
        "/api/v1/trials/NCT90000001", json={"locations": [{"country": "Belgium"}]}, headers=auth
    )
    assert [loc["country"] for loc in response.json()["locations"]] == ["Belgium"]


def test_patch_cannot_null_required_fields(client, auth):
    response = client.patch("/api/v1/trials/NCT90000001", json={"title": None}, headers=auth)
    assert response.status_code == 422


def test_delete_trial(client, auth):
    assert client.delete("/api/v1/trials/NCT90000001", headers=auth).status_code == 204
    assert client.get("/api/v1/trials/NCT90000001").status_code == 404
    assert client.delete("/api/v1/trials/NCT90000001", headers=auth).status_code == 404
