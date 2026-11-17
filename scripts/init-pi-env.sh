#!/usr/bin/env bash
# Létrehozza a pi/.env-et a pi/.env.example alapján, friss Authelia-titkokkal. Meglévő fájlt nem ír felül.
# A domaint, a Cloudflare-tokent, a Tailscale-címet és a worker tokenjét kézzel kell kitölteni.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
target=${1:-$repo_root/pi/.env}

if [[ -e $target ]]; then
  echo "A $target már létezik, nem írom felül." >&2
  exit 1
fi

umask 077
cp "$repo_root/pi/.env.example" "$target"

set_value() {
  sed -i "s|^$1=\$|$1=$2|" "$target"
}

set_value AUTHELIA_SESSION_SECRET "$(openssl rand -hex 32)"
set_value AUTHELIA_STORAGE_ENCRYPTION_KEY "$(openssl rand -hex 32)"
set_value AUTHELIA_JWT_SECRET "$(openssl rand -hex 32)"

echo "Kész: $target"
echo "Töltsd ki: FINANCE_DOMAIN, CLOUDFLARE_API_TOKEN, BIND_ADDRESS,"
echo "WORKER_API_TOKEN (a home/.env-ből), HOUSEHOLD_MEMBERS, REPORTS_URL."
