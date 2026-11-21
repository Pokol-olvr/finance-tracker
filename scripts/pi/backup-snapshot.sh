#!/usr/bin/env bash
# A Pi mentése tar-ként a kimenetre: az Authelia adata és a pi/.env, mert az Authelia a
# TOTP-titkokat a benne lévő kulccsal titkosítja. A backup-user.sh telepíti
# /usr/local/sbin/finance-pi-snapshot néven; a mentes felhasználó kulcsa csak ezt futtatja.
#
#   sudo finance-pi-snapshot > pi.tar
#
# A repón kívüli szolgáltatások saját mentése az /etc/finance-pi-snapshot.d mappába tehető:
# minden root tulajdonú, csak root által írható futtatható fájl lefut, egy üres mappa
# argumentummal, és amit oda ír, az extra/<fájlnév> alatt kerül a mentésbe.
set -euo pipefail

repo=${FINANCE_REPO:?a repó helye}
data=$(grep -s '^DATA_DIR=' "$repo/pi/.env" | cut -d= -f2-) || true
data=${data:-$repo/pi/data}
hooks=/etc/finance-pi-snapshot.d

umask 077
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/authelia"

# Az SQLite-ot a backup API másolja, így futó szolgáltatás mellett is egységes a pillanatkép.
python3 - "$data/authelia/db.sqlite3" "$work/authelia/db.sqlite3" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
source.backup(target)
target.close()
source.close()
PY

cp -p "$data/authelia/users_database.yml" "$work/authelia/"
cp -p "$repo/pi/.env" "$work/pi.env"

# Csak root által írható kiegészítők futnak, mert a parancs rootként fut.
if [[ -d $hooks ]]; then
  if [[ $(stat -c '%u %a' "$hooks") =~ ^0\ [0-7][0145][0145]$ ]]; then
    while IFS= read -r -d '' hook; do
      name=$(basename "$hook")
      [[ $name =~ ^[a-z0-9_-]+$ ]] || continue
      mkdir -p "$work/extra/$name"
      "$hook" "$work/extra/$name"
    done < <(find "$hooks" -maxdepth 1 -type f -user root -perm -u+x ! -perm /022 -print0 | sort -z)
  else
    echo "A $hooks nem csak root által írható, kihagyva." >&2
  fi
fi

date -u +%FT%TZ >"$work/created_at"
tar -C "$work" -cf - .
