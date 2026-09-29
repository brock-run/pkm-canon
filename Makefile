.PHONY: help test lint schemas-check check

help:
	@printf 'Targets: test, lint, schemas-check, check\n'

test:
	./.venv/bin/pytest -q

lint:
	./.venv/bin/ruff check src tests scripts

schemas-check:
	./.venv/bin/python scripts/generate_schemas.py --check

check: schemas-check lint test
