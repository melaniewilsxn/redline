.PHONY: install test lint format db-up db-down dev seed reseed bench ui-install ui ui-test ui-lint ui-types

PORT ?= 8000

install:
	cd backend && uv sync

test:
	cd backend && uv run --env-file ../.env pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

format:
	cd backend && uv run ruff format . && uv run ruff check --fix .

db-up:
	docker compose up -d --wait

db-down:
	docker compose down

dev:
	cd backend && uv run --env-file ../.env uvicorn redline.main:build_app --factory --reload --port $(PORT) --no-access-log

seed:
	cd backend && uv run --env-file ../.env python scripts/seed.py

reseed:
	cd backend && uv run --env-file ../.env python scripts/seed.py --reset

bench:
	cd backend && uv run python -m scripts.benchmark

ui-install:
	cd frontend && npm install

ui:
	cd frontend && REDLINE_API_URL=http://localhost:$(PORT) npm run dev

ui-test:
	cd frontend && npm test

ui-lint:
	cd frontend && npm run lint

ui-types:
	cd frontend && REDLINE_API_URL=http://localhost:$(PORT) npm run generate:api-types
