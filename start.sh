#!/bin/bash
set -e

docker compose up -d db

until docker compose exec db psql -U postgres -c "SELECT 1" > /dev/null 2>&1; do
    echo "  Still waiting..."
    sleep 2
done

docker compose exec -T db psql -U postgres -d pharmacogenomic_data < backup.sql

docker compose up app