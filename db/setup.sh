#!/bin/bash
# (Re)creates the lineup database from create.sql and loads the seed data.
# Uses the PG* environment variables for the connection. Usage: db/setup.sh
set -e
cd "$(dirname "$0")"
DB_NAME="${DB_NAME:-lineup}"
dropdb --if-exists "$DB_NAME"
createdb "$DB_NAME"
psql -v ON_ERROR_STOP=1 -q -d "$DB_NAME" -f create.sql
psql -v ON_ERROR_STOP=1 -q -d "$DB_NAME" -f load.sql
echo "database $DB_NAME ready"
