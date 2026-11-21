.PHONY: setup up down migrate seed logs worker-logs shell-api shell-worker test pull-model clean help

# Setup
setup:
	@echo "Setting up HydraClip..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi
	@echo "Building Docker images..."
	docker-compose build
	@echo "Setup complete. Run 'make up' to start services."

# Docker Compose
up:
	docker-compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@echo "Services started. API: http://localhost:8000, Web: http://localhost:3000"

down:
	docker-compose down

logs:
	docker-compose logs -f

worker-logs:
	docker-compose logs -f worker

# Database
migrate:
	docker-compose exec api alembic upgrade head

seed:
	docker-compose exec api python seed.py

# Shells
shell-api:
	docker-compose exec api bash

shell-worker:
	docker-compose exec worker bash

# Testing
test:
	docker-compose exec api pytest -v

# Models
pull-model:
	docker-compose exec ollama ollama pull llama3.2

# Cleanup
clean:
	docker-compose down -v
	@echo "All containers and volumes removed."

# Help
help:
	@echo "HydraClip Makefile commands:"
	@echo "  make setup       - Copy .env and build images"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make migrate     - Run database migrations"
	@echo "  make seed        - Seed database with initial data"
	@echo "  make logs        - Tail all logs"
	@echo "  make worker-logs - Tail worker logs"
	@echo "  make shell-api   - Shell into API container"
	@echo "  make shell-worker- Shell into worker container"
	@echo "  make test        - Run tests"
	@echo "  make pull-model  - Pull default Ollama model"
	@echo "  make clean       - Remove all containers and volumes"