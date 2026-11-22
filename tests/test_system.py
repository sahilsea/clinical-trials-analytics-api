def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_responses_carry_request_id_and_timing(client):
    response = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_root_redirects_to_docs(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_openapi_schema_lists_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/trials" in paths
    assert "/api/v1/analytics/summary" in paths


def test_etl_runs_endpoint(client):
    runs = client.get("/api/v1/etl-runs").json()
    assert runs[0]["status"] == "success"
    assert runs[0]["inserted"] == 11
