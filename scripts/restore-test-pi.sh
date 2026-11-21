#!/usr/bin/env bash
# A Pi legutóbbi mentésének visszaállítási próbája: a restic pi pillanatképéből egy ideiglenes
# mappába, minden benne lévő SQLite-adatbázis ellenőrzésével. Az éles Pi-hez nem nyúl.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

engine=${COMPOSE%% *}
name=restore-pi.$$
work=$BACKUP_DIR/$name

cleanup() {
  # A restic rootként állít vissza, ezért a törlés is konténerben fut.
  if [[ -d $work ]]; then
    $engine run --rm -v "$(cd "$work" && pwd):/w" docker.io/library/alpine:3.22 \
      sh -c 'rm -rf /w/* /w/.[!.]*' >/dev/null
    rmdir "$work"
  fi
}
trap cleanup EXIT

mkdir -p "$work"
compose run --rm restic restore latest --tag pi --target "/backup/$name" | tail -1
src=$work/backup/pi
echo "A mentés ideje: $(cat "$src/created_at")"

python3 - "$src" <<'PY'
import pathlib
import sqlite3
import sys

src = pathlib.Path(sys.argv[1])
dbs = sorted(src.rglob("*.sqlite3"))
assert src / "authelia/db.sqlite3" in dbs, "az Authelia adatbázisa hiányzik"
for path in dbs:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    assert db.execute("pragma integrity_check").fetchone()[0] == "ok", path
    print("rendben:", path.relative_to(src))
au = sqlite3.connect(f"file:{src}/authelia/db.sqlite3?mode=ro", uri=True)
print("Authelia: TOTP", au.execute("select count(*) from totp_configurations").fetchone()[0])
extra = src / "extra"
if extra.is_dir():
    print("Kiegészítők:", ", ".join(sorted(p.name for p in extra.iterdir())))
PY

echo "Kész: a Pi mentése visszaállítható."
