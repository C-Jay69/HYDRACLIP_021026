.PHONY: help setup up down logs ps migrate revision seed model test lint shell-api shell-db \
        venv install dev clean

# The previous Makefile drove Python tooling through Bun
# (`bun run --cwd apps/api alembic upgrade head`, `bun run --cwd apps/api bash`),
# which cannot work — Bun does not execute Python or spawn container shells.
# Container tasks now go through `docker compose exec`; local tasks use the venv.

VENV        ?= .venv
PY          := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
PYTEST      := $(VENV)/bin/pytest
UVICORN     := $(VENV)/bin/uvicorn
COMPOSE     := docker compose
ALEMBIC_CFG := apps/api/alembic.ini
OLLAMA_MODEL ?= llama3.2

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "} {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

# --- Docker -------------------------------------------------------------------

setup: ## Copy .env and build images
	@test -f .env || cp .env.example .env
	$(COMPOSE) build

up: ## Start all services
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

ps: ## Show service status
	$(COMPOSE) ps

logs: ## Tail all logs
	$(COMPOSE) logs -f

shell-api: ## Shell into the api container
	$(COMPOSE) exec api bash

shell-db: ## psql into Postgres
	$(COMPOSE) exec postgres psql -U videoforce -d videoforce

migrate: ## Apply migrations inside the api container
	$(COMPOSE) exec api alembic -c $(ALEMBIC_CFG) upgrade head

revision: ## Autogenerate a migration: make revision m="add table"
	$(COMPOSE) exec api alembic -c $(ALEMBIC_CFG) revision --autogenerate -m "$(m)"

seed: ## Seed the database inside the api container
	$(COMPOSE) exec api python seed.py

model: ## Pull the default Ollama model
	$(COMPOSE) exec ollama ollama pull $(OLLAMA_MODEL)

# --- Local development --------------------------------------------------------

venv: ## Create the local virtualenv
	python3 -m venv $(VENV)

install: venv ## Install Python dependencies locally
	$(PIP) install --upgrade pip
	$(PIP) install -r apps/api/requirements-dev.txt

dev: ## Run the API locally with reload
	$(UVICORN) apps.api.main:app --host 0.0.0.0 --port 8000 --reload

test: ## Run the backend test suite
	$(PYTEST)

migrate-local: ## Apply migrations against DATABASE_URL on the host
	$(VENV)/bin/alembic -c $(ALEMBIC_CFG) upgrade head

seed-local: ## Seed the database on the host
	$(PY) seed.py

clean: ## Remove caches and build artefacts
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
