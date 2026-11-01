#!/usr/bin/env bash
# Csak üres adatkönyvtárnál fut le. A sémákat és a jogokat a migrations/ kezeli.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v finance_owner_pw="$FINANCE_OWNER_PASSWORD" \
  -v app_writer_pw="$APP_WRITER_PASSWORD" \
  -v dbt_runner_pw="$DBT_RUNNER_PASSWORD" \
  -v report_reader_pw="$REPORT_READER_PASSWORD" <<'SQL'
create role finance_owner login password :'finance_owner_pw';
create role app_writer login password :'app_writer_pw';
create role dbt_runner login password :'dbt_runner_pw';
create role report_reader login password :'report_reader_pw';

-- A migráció így állíthatja be a dbt_runner által később létrehozott táblák jogait.
grant dbt_runner to finance_owner;

create database finance owner finance_owner;

revoke all on database finance from public;
grant connect on database finance to app_writer, dbt_runner, report_reader;

\connect finance
-- A sémákhoz minden szerepkör külön kap jogot, a publichoz senki.
revoke all on schema public from public;
SQL
