#!/usr/bin/env bash
# Visszaállítási próba: a legutóbbi pillanatképet egy eldobható Postgresbe tölti,
# és a sorok számát a mentéskor rögzítettel veti össze. Az élő adathoz nem nyúl.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

work=/backup/restore
dumps=$work/backup/dumps

cleanup() {
  compose rm -sf restore-db >/dev/null 2>&1 || true
  compose run --rm --entrypoint rm restic -rf "$work" >/dev/null 2>&1 || true
}
trap cleanup EXIT

compose run --rm restic check
compose run --rm restic restore latest --target "$work" --include /backup/dumps

compose up -d restore-db
for _ in {1..60}; do
  compose exec -T restore-db pg_isready -q -h 127.0.0.1 -U postgres && break
  sleep 1
done

compose exec -T restore-db createdb -U postgres finance
compose exec -T restore-db pg_restore -U postgres -d finance \
  --no-owner --no-privileges --exit-on-error "$dumps/finance.dump"

expected=$(compose exec -T restore-db cat "$dumps/finance.rowcounts")
actual=$(row_counts restore-db)

if [[ -z $expected ]]; then
  echo "A mentésben nincs sorszám-lista." >&2
  exit 1
fi

if ! diff <(echo "$expected") <(echo "$actual"); then
  echo "A visszaállított sorszámok eltérnek a mentéskor rögzítettektől." >&2
  exit 1
fi

echo "A visszaállítási próba sikeres: $(wc -l <<<"$actual") finance tábla egyezik."
