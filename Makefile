.PHONY: install dev test coverage lint

install:
	python -m pip install -e '.[dev]'

dev:
	SEED_DEMO_DATA=true uvicorn app.main:app --reload

test:
	pytest

coverage:
	pytest --cov-report=term-missing

lint:
	ruff check app tests
