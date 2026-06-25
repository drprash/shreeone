#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

cleanup() {
    echo "Cleaning up test containers and volumes..."
    docker compose -f docker-compose.test.yml down --volumes --remove-orphans --timeout 10 2>/dev/null || true
    # Remove Python cache artifacts written into the mounted backend volume
    find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find backend -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    # Remove frontend build artifacts written into the mounted frontend volume
    rm -rf frontend/node_modules frontend/dist
}
trap cleanup EXIT

echo "Running backend tests in python:3.12-slim (via docker-compose.test.yml)..."
docker compose -f docker-compose.test.yml run --rm backend-test

echo "Running frontend build validation in node:22-alpine (via docker-compose.test.yml)..."
docker compose -f docker-compose.test.yml run --rm frontend-test

echo "Containerized test checks completed successfully."
