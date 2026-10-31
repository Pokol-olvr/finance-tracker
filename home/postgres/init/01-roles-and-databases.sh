#!/usr/bin/env bash
# Csak üres adatkönyvtárnál fut le. A sémákat és a jogokat a migrations/ kezeli.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v finance_owner_pw="$FINANCE_OWNER_PASSWORD" \
  -v app_writer_pw="$APP_WRITER_PASSWORD" \
  -v dbt_runner_pw="$DBT_RUNNER_PASSWORD" \
  -v mb_reader_pw="$MB_READER_PASSWORD" \
  -v metabase_pw="$METABASE_DB_PASSWORD" <<'SQL'
create role finance_owner login password :'finance_owner_pw';
create role app_writer login password :'app_writer_pw';
create role dbt_runner login password :'dbt_runner_pw';
create role mb_reader login password :'mb_reader_pw';
create role metabase_owner login password :'metabase_pw';

-- A migráció így állíthatja be a dbt_runner által később létrehozott táblák jogait.
grant dbt_runner to finance_owner;

create database finance owner finance_owner;
create database metabase owner metabase_owner;

revoke all on database finance from public;
revoke all on database metabase from public;
grant connect on database finance to app_writer, dbt_runner, mb_reader;

\connect finance
-- A sémákhoz minden szerepkör külön kap jogot, a publichoz senki.
revoke all on schema public from public;
SQL
