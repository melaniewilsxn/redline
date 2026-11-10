.PHONY: install test lint format db-up db-down dev seed

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
	cd backend && uv run --env-file ../.env uvicorn redline.main:build_app --factory --reload

seed:
	cd backend && uv run --env-file ../.env python scripts/seed.py
