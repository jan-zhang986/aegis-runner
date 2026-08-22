#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deployments/docker/docker-compose.e2e.yml"

cleanup() {
  docker compose -f "$COMPOSE_FILE" down -v >/dev/null 2>&1 || true
}

trap cleanup EXIT

cd "$ROOT_DIR"

docker compose -f "$COMPOSE_FILE" up -d --build mysql redis kafka
docker compose -f "$COMPOSE_FILE" up -d --wait mysql redis kafka

DB_PRIMARY_URL="mysql+asyncmy://root:root@127.0.0.1:13306/aegis_runner_e2e?charset=utf8mb4" \
KAFKA_BOOTSTRAP_SERVERS="127.0.0.1:19092" \
.venv/bin/python deployments/scripts/init-e2e-environment.py

docker compose -f "$COMPOSE_FILE" up -d --build master worker

ENABLE_BUSINESS_E2E=1 \
MASTER_E2E_BASE_URL="http://127.0.0.1:18100" \
MASTER_API_TOKEN="e2e-master-token" \
MYSQL_E2E_HOST="127.0.0.1" \
MYSQL_E2E_PORT="13306" \
MYSQL_E2E_USER="root" \
MYSQL_E2E_PASSWORD="root" \
MYSQL_E2E_DATABASE="aegis_runner_e2e" \
REDIS_E2E_HOST="127.0.0.1" \
REDIS_E2E_PORT="16379" \
.venv/bin/python -m pytest tests/e2e/test_workflow_e2e.py tests/e2e/test_lifecycle_e2e.py
