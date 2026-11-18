#!/usr/bin/env bash
# A Pi mentése tar-ként a kimenetre: a Vaultwarden és az Authelia adata, és a pi/.env, mert az
# Authelia a TOTP-titkokat a benne lévő kulccsal titkosítja. A backup-user.sh telepíti
# /usr/local/sbin/finance-pi-snapshot néven; a mentes felhasználó kulcsa csak ezt futtathatja.
#
#   sudo finance-pi-snapshot > pi.tar
set -euo pipefail

repo=${FINANCE_REPO:?a repó helye}
data=$(grep -s '^DATA_DIR=' "$repo/pi/.env" | cut -d= -f2-) || true
data=${data:-$repo/pi/data}

umask 077
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/vaultwarden" "$work/authelia"

# Az SQLite-ot a backup API másolja, így futó szolgáltatás mellett is egységes a pillanatkép.
python3 - "$data" "$work" <<'PY'
import sqlite3
import sys

data, work = sys.argv[1:]
for name in ("vaultwarden", "authelia"):
    source = sqlite3.connect(f"{data}/{name}/db.sqlite3")
    target = sqlite3.connect(f"{work}/{name}/db.sqlite3")
    source.backup(target)
    target.close()
    source.close()
PY

# A Vaultwarden többi része: kulcs, csatolmányok, küldések; az ikon-gyorsítótár nem kell.
tar -C "$data/vaultwarden" --exclude='./db.sqlite3*' --exclude=./icon_cache --exclude=./tmp -cf - . |
  tar -C "$work/vaultwarden" -xf -
cp -p "$data/authelia/users_database.yml" "$work/authelia/"
cp -p "$repo/pi/.env" "$work/pi.env"
date -u +%FT%TZ >"$work/created_at"

tar -C "$work" -cf - .
