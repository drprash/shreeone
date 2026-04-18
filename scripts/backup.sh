#!/usr/bin/env bash
# Run from the project root or via cron — backs up the shreeone database,
# compresses the dump, and retains the last 7 days of backups.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/shreeone_backup_${DATE}.sql.gz"

mkdir -p "$BACKUP_DIR"

# Load credentials from .env so DB_USER / DB_NAME are available
if [[ -f "${PROJECT_DIR}/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "${PROJECT_DIR}/.env"
    set +a
fi

DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-shreeone}"

echo "Starting backup at ${DATE}..."

docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
    pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

find "$BACKUP_DIR" -name "shreeone_backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: ${BACKUP_FILE}"
