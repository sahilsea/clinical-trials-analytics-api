# Clinical Trials Analytics API

A REST API for searching and analysing 5,783 COVID-19 clinical trials from ClinicalTrials.gov, built with **FastAPI**, **SQLAlchemy 2.0** and **PostgreSQL**. It includes an **ETL pipeline** that cleans and validates the raw CSV export, and a **test suite** that covers 98% of the code.

The project started as a pandas notebook for exploring the data ([`notebooks/`](notebooks/covid_trials_eda.ipynb)). I then rebuilt it as a backend service: the notebook's cleaning steps became a repeatable pipeline, and its charts became API endpoints that return JSON.

```mermaid
flowchart LR
    CSV[ClinicalTrials.gov<br/>CSV export] --> E[Extract<br/>column checks]
    E --> T[Transform<br/>clean + Pydantic validation]
    T -->|rejected rows| R[rejects.csv]
    T --> L[Load<br/>batched upsert]
    L --> DB[(PostgreSQL / SQLite)]
    DB --> API[FastAPI]
    API --> C[Clients / Swagger UI]
```

## Features

**API**
- `GET /api/v1/trials`: full-text search, 12 combinable filters (status, phase, country, age group, enrollment range, date range, and more), sorting and pagination
- `GET /api/v1/trials/{nct_number}`: trial details with structured locations
- `POST` / `PATCH` / `DELETE`: write endpoints protected by an API key, with request validation, `409` on duplicates and partial updates
- `/api/v1/analytics/*`: summary statistics, distributions, top countries, monthly or yearly timelines, age-group coverage and enrollment by phase. **Every analytics endpoint accepts the same filters as the trials list**, so `?country=India&phase=Phase 3` works everywhere.
- `/health` (checks the database connection) and `/api/v1/etl-runs` (pipeline audit log)
- Auto-generated OpenAPI docs at `/docs`
- A request ID and timing header on every response, plus structured request logging

**ETL pipeline**
- Checks that the CSV has the required columns before processing
- Parses messy fields: eligibility text (`"18 Years to 80 Years (Adult, Older Adult)"`) into numeric age bounds and age-group flags, `"Facility, City, State, Country"` strings into a separate `trial_locations` table, pipe-delimited lists, and mixed date formats
- Validates every row against the **same Pydantic schema the API uses**, so data loaded from the CSV follows the same rules as data posted to the API
- Idempotent batched upserts in a single transaction: re-running the pipeline updates rows instead of duplicating them, and a failed run leaves the database unchanged
- Writes rejected rows to a report and records each run (row counts, status, errors) in an `etl_runs` table
- `--dry-run` mode validates the file without writing anything

**Engineering**
- Layered structure: routes → repository/services → ORM models, with the parsing rules in one shared module
- Database aggregations (`GROUP BY`, `COUNT DISTINCT`, `AVG`) instead of loading rows into Python, with dialect-aware date truncation for both PostgreSQL and SQLite
- 84 pytest tests (unit + integration), 98% coverage
- Docker image (non-root user, health check) and Docker Compose with PostgreSQL
- GitHub Actions CI: ruff lint/format, the test suite on **both SQLite and PostgreSQL**, and a Docker build

## Tech stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · PostgreSQL · pandas · pytest · Docker · GitHub Actions · Ruff

## Quick start

### 1. Get the dataset

Download `COVID_clinical_trials.csv` from the [COVID-19 Clinical Trials dataset on Kaggle](https://www.kaggle.com/datasets/parulpandey/covid19-clinical-trials-dataset) and save it as `data/COVID_clinical_trials.csv`.

### 2a. Run locally (SQLite, no setup)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m etl.pipeline data/COVID_clinical_trials.csv --rejects rejects.csv
uvicorn app.main:app --reload
```

Then open http://localhost:8000/docs.

### 2b. Run with Docker (PostgreSQL)

```bash
docker compose up --build -d      # API + PostgreSQL
docker compose run --rm etl       # load the CSV
```

## Example requests

```bash
# Recruiting Phase 3 trials in the United States, largest first
curl "localhost:8000/api/v1/trials?status=Recruiting&phase=Phase%203&country=United%20States&sort_by=enrollment&order=desc"

# Search
curl "localhost:8000/api/v1/trials?q=plasma&page_size=5"

# Headline numbers, and the same numbers for trials that include children
curl "localhost:8000/api/v1/analytics/summary"
curl "localhost:8000/api/v1/analytics/summary?age_group=child"

# Trials started per month, top 10 countries
curl "localhost:8000/api/v1/analytics/timeline?granularity=month"
curl "localhost:8000/api/v1/analytics/countries?limit=10"

# Create a trial (needs the API key from .env)
curl -X POST localhost:8000/api/v1/trials \
  -H "X-API-Key: change-me" -H "Content-Type: application/json" \
  -d '{"nct_number": "NCT99999999", "title": "My trial", "status": "Recruiting"}'
```

## Project structure

```
app/
  main.py              App factory, middleware, error handling
  config.py            Settings from environment variables
  database.py          Engine and session management
  models.py            ORM models: Trial, TrialLocation, EtlRun
  schemas.py           Pydantic request/response models
  parsing.py           Domain parsing rules (shared by API and ETL)
  filters.py           Reusable query filters
  repository.py        Data access for trials
  services/analytics.py  Aggregation queries
  api/deps.py          Auth, filter and pagination dependencies
  api/routes/          trials, analytics, system
etl/
  extract.py → transform.py → load.py, orchestrated by pipeline.py
tests/                 84 tests + a synthetic fixture CSV
notebooks/             Original exploratory analysis
```

## Design decisions

- **Missing values stay missing.** The notebook filled missing enrollment with the median, which is fine for a chart. A system of record should not invent data, so the database keeps `NULL`s and the analytics endpoints compute over known values.
- **One validation path.** The ETL runs every CSV row through the API's `TrialCreate` schema, so the rules can't drift apart.
- **Locations are normalised** into their own table because "trials per country" needs a `COUNT(DISTINCT trial_id)` across a one-to-many relationship. Searching a text column with `LIKE` would get this wrong.
- **Sync SQLAlchemy.** FastAPI runs sync endpoints in a threadpool, and the workload is simple read queries, so async drivers would add complexity without a real benefit at this scale.
- **Tests use the real pipeline.** API tests seed the database by running the ETL on a fixture CSV, so each run also works as an end-to-end test.

## Development

```bash
make test       # pytest with coverage
make lint       # ruff
make format
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost/test pytest   # run tests against PostgreSQL
```

## Possible next steps

- Alembic migrations instead of `create_all`
- Scheduled incremental sync from the ClinicalTrials.gov API v2
- Redis caching for analytics responses
- PostgreSQL full-text search (`tsvector`) instead of `ILIKE`
