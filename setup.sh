#!/bin/bash
set -e

docker compose up -d db

until docker compose exec db psql -U postgres -c "SELECT 1" > /dev/null 2>&1; do
    echo "  Still waiting..."
    sleep 2
done
docker compose exec -T db psql -U postgres -d pharmacogenomic_data < backup.sql

mkdir -p logs

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CRON_JOB="0 2 6 2,4,6,8,10,12 * $REPO_DIR/venv/bin/python3 $REPO_DIR/loaders/updating_dates.py >> $REPO_DIR/logs/update.log 2>&1"
( crontab -l 2>/dev/null | grep -v "updating_dates.py"; echo "$CRON_JOB" ) | crontab -
echo "Cron job registered."

docker compose up app
