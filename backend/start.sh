#!/usr/bin/env bash
#
# Imad backend startup: apply pending Alembic migrations, then serve the API.
# The worker service overrides this entrypoint (see docker-compose.yml) and
# runs `python -m app.core.worker` instead.
set -e

# Apply any pending schema migrations (no-op until ORM migrations are added).
alembic upgrade head

uvicorn app.main:app --host 0.0.0.0 --port 8000