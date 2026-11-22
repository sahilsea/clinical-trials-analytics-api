.PHONY: install run etl test lint format docker-up docker-etl docker-down

CSV ?= data/COVID_clinical_trials.csv

install:
	pip install -e ".[dev]"

run:
	uvicorn app.main:app --reload

etl:
	python -m etl.pipeline $(CSV) --rejects rejects.csv

test:
	pytest --cov --cov-report=term-missing

lint:
	ruff check . && ruff format --check .

format:
	ruff format . && ruff check --fix .

docker-up:
	docker compose up --build -d

docker-etl:
	docker compose run --rm etl

docker-down:
	docker compose down
