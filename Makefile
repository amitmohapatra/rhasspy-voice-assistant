# =============================================================================
# Rhasspy Voice Assistant - Makefile
# =============================================================================
# Multi-cloud local development and deployment commands.
#
# Usage:
#   make up          - Start with local filesystem storage (no emulators)
#   make up-aws      - Start with AWS emulation (LocalStack)
#   make up-azure    - Start with Azure emulation (Azurite)
#   make up-gcp      - Start with GCP emulation (fake-gcs-server)
#   make down        - Stop all services
#   make logs        - View logs
#   make test        - Run tests
# =============================================================================

.PHONY: up up-aws up-azure up-gcp down logs migrate test shell psql clean build help

COMPOSE = docker compose

# ---------------------------------------------------------------------------
# Start services
# ---------------------------------------------------------------------------

## Start with local filesystem storage (no cloud emulators)
up:
	$(COMPOSE) --env-file .env.local up -d

## Start with AWS emulation via LocalStack
up-aws:
	$(COMPOSE) --env-file .env.aws --profile aws up -d

## Start with Azure emulation via Azurite
up-azure:
	$(COMPOSE) --env-file .env.azure --profile azure up -d

## Start with GCP emulation via fake-gcs-server
up-gcp:
	$(COMPOSE) --env-file .env.gcp --profile gcp up -d

# ---------------------------------------------------------------------------
# Stop / manage services
# ---------------------------------------------------------------------------

## Stop all services
down:
	$(COMPOSE) --profile aws --profile azure --profile gcp down

## View logs (all services)
logs:
	$(COMPOSE) --profile aws --profile azure --profile gcp logs -f

## View backend logs only
logs-backend:
	$(COMPOSE) logs -f backend

## Run database migrations
migrate:
	$(COMPOSE) exec backend alembic upgrade head

## Run tests
test:
	$(COMPOSE) exec backend pytest

## Open a shell in the backend container
shell:
	$(COMPOSE) exec backend bash

## Open a PostgreSQL shell
psql:
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-rhasspy} -d $${POSTGRES_DB:-rhasspy}

## Remove all volumes and clean up
clean:
	$(COMPOSE) --profile aws --profile azure --profile gcp down -v --remove-orphans

## Rebuild all images
build:
	$(COMPOSE) build

## Rebuild and start with local storage
rebuild: build up

# ---------------------------------------------------------------------------
# Cloud-specific initialization helpers
# ---------------------------------------------------------------------------

## Initialize Azure containers (run after up-azure)
init-azure:
	$(COMPOSE) exec azurite sh /docker/azurite/init-azure.sh 2>/dev/null || \
		bash docker/azurite/init-azure.sh

## Initialize GCP buckets (run after up-gcp)
init-gcp:
	bash docker/gcp/init-gcp.sh

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

## Show this help
help:
	@echo "Rhasspy Voice Assistant - Development Commands"
	@echo ""
	@echo "Start services:"
	@echo "  make up          Start with local filesystem storage"
	@echo "  make up-aws      Start with AWS emulation (LocalStack)"
	@echo "  make up-azure    Start with Azure emulation (Azurite)"
	@echo "  make up-gcp      Start with GCP emulation (fake-gcs-server)"
	@echo ""
	@echo "Manage services:"
	@echo "  make down        Stop all services"
	@echo "  make logs        View logs (all services)"
	@echo "  make logs-backend  View backend logs only"
	@echo "  make clean       Remove all volumes and clean up"
	@echo "  make build       Rebuild all images"
	@echo "  make rebuild     Rebuild and start with local storage"
	@echo ""
	@echo "Development:"
	@echo "  make migrate     Run database migrations"
	@echo "  make test        Run tests"
	@echo "  make shell       Backend shell"
	@echo "  make psql        PostgreSQL shell"
	@echo ""
	@echo "Cloud init:"
	@echo "  make init-azure  Create Azure containers (after up-azure)"
	@echo "  make init-gcp    Create GCP buckets (after up-gcp)"
