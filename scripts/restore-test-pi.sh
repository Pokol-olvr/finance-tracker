#!/usr/bin/env bash
# A Pi legutóbbi mentésének visszaállítási próbája: a restic pi pillanatképéből egy ideiglenes
# mappába, adatbázis-ellenőrzéssel, és egy eldobható Vaultwarden indul rajta, port nélkül.
# Az éles Pi-hez nem nyúl.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

image=$(sed -n 's/^ *image: *\(docker.io\/vaultwarden\/server:.*\)$/\1/p' "$REPO_ROOT/pi/docker-compose.yml")
engine=${COMPOSE%% *}
name=restore-pi.$$
work=$BACKUP_DIR/$name
container=finance-restore-pi-$$

cleanup() {
  $engine rm -f "$container" >/dev/null 2>&1 || true
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
import sqlite3
import sys

src = sys.argv[1]
vw = sqlite3.connect(f"file:{src}/vaultwarden/db.sqlite3?mode=ro", uri=True)
au = sqlite3.connect(f"file:{src}/authelia/db.sqlite3?mode=ro", uri=True)
for db in (vw, au):
    assert db.execute("pragma integrity_check").fetchone()[0] == "ok"
print("Vaultwarden: felhasználó", vw.execute("select count(*) from users").fetchone()[0],
      "· bejegyzés", vw.execute("select count(*) from ciphers").fetchone()[0])
print("Authelia: TOTP", au.execute("select count(*) from totp_configurations").fetchone()[0])
PY

mkdir -p "$work/vw"
cp -a "$src/vaultwarden/." "$work/vw/"
$engine run -d --name "$container" -v "$(cd "$work/vw" && pwd):/data" "$image" >/dev/null
for _ in $(seq 45); do
  state=$($engine inspect -f '{{.State.Health.Status}}' "$container")
  [[ $state == healthy ]] && break
  sleep 2
done
[[ $state == healthy ]] || {
  echo "Az eldobható Vaultwarden nem indult el." >&2
  exit 1
}
echo "Kész: a Pi mentése visszaállítható, a Vaultwarden elindul rajta."
