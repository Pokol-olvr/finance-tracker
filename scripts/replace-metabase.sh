#!/usr/bin/env bash
# Egyszeri lépés a Metabase kivezetéséhez, a v0.5.0-ra frissítéskor; ismételve sem árt.
# Előtte legyen friss mentés: scripts/backup.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

# A szerepkör megmarad, de friss jelszót kap, ami már megvan, azt nem írja felül.
if ! grep -q '^REPORT_READER_PASSWORD=.' "$ENV_FILE"; then
  REPORT_READER_PASSWORD=$(openssl rand -hex 24)
  sed -i '/^REPORT_READER_PASSWORD=/d' "$ENV_FILE"
  printf 'REPORT_READER_PASSWORD=%s\n' "$REPORT_READER_PASSWORD" >>"$ENV_FILE"
  export REPORT_READER_PASSWORD
fi

compose up -d --remove-orphans postgres
compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
  -v password="$REPORT_READER_PASSWORD" <<'SQL'
select exists (select 1 from pg_roles where rolname = 'mb_reader') as has_old_role \gset
\if :has_old_role
  alter role mb_reader rename to report_reader;
\endif
alter role report_reader password :'password';
drop database if exists metabase;
drop role if exists metabase_owner;
SQL

echo "A Metabase kikerült, a riportfelület a report_reader szerepkört használja."
