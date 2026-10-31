#!/usr/bin/env bash
# Létrehozza a .env-et a .env.example alapján, friss titkokkal. Meglévő fájlt nem ír felül.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
target=${1:-$repo_root/home/.env}

if [[ -e $target ]]; then
  echo "A $target már létezik, nem írom felül." >&2
  exit 1
fi

hex() { openssl rand -hex "$1"; }

umask 077
cp "$repo_root/home/.env.example" "$target"

set_value() {
  sed -i "s|^$1=\$|$1=$2|" "$target"
}

for name in POSTGRES_PASSWORD FINANCE_OWNER_PASSWORD APP_WRITER_PASSWORD \
  DBT_RUNNER_PASSWORD MB_READER_PASSWORD METABASE_DB_PASSWORD \
  MB_ENCRYPTION_SECRET_KEY GARAGE_ADMIN_TOKEN RESTIC_PASSWORD; do
  set_value "$name" "$(hex 24)"
done

set_value GARAGE_RPC_SECRET "$(hex 32)"
set_value GARAGE_ACCESS_KEY "GK$(hex 12)"
set_value GARAGE_SECRET_KEY "$(hex 32)"

echo "Kész: $target"
echo "Az MB_ENCRYPTION_SECRET_KEY és a RESTIC_PASSWORD értékét mentsd el a jelszókezelőbe."
