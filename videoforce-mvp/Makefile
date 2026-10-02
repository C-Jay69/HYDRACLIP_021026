.PHONY: setup up down migrate seed model test logs worker-logs shell-api shell-worker help

setup: ## Copy .env, build docker images
	@cp .env.example .env
	@docker compose build

up: ## Start all services docker-compose up -d
	docker compose up -d

down: ## Stop all services docker-compose down
	docker compose down

migrate: ## Run alembic upgrade head
	bun run --cwd apps/api alembic upgrade head

seed: ## Run seed.py
	bun run --cwd apps/api seed.py

model: ## Pull default Ollama model
	bun run pull-model

test: ## Run tests
	bun test

logs: ## Tail all logs
	docker compose logs -f

worker-logs: ## Tail worker logs
	docker compose logs -f worker

shell-api: ## Exec into api container
	bun run --cwd apps/api bash

shell-worker: ## Exec into worker container
	bun run --cwd apps/worker bash

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "} {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'