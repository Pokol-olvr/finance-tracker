#!/usr/bin/env bash
# Napi mentés: adatbázis-dumpok, a Garage raw bucket tükre, majd restic pillanatkép.
# A futó stacket igényli.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

# A dumpok pénzügyi adatot tartalmaznak.
umask 077

dumps=$BACKUP_DIR/dumps
mkdir -p "$dumps" "$BACKUP_DIR/garage-raw" "$RESTIC_REPO_DIR"

if [[ $RESTIC_REPO_DIR == ./backup/restic ]]; then
  echo "Figyelem: a restic tároló ugyanazon a lemezen van, állítsd be a RESTIC_REPO_DIR-t." >&2
fi

compose exec -T postgres pg_dump -Fc -U postgres finance >"$dumps/finance.dump.tmp"
mv "$dumps/finance.dump.tmp" "$dumps/finance.dump"

# A visszaállítási próba ehhez hasonlítja a visszatöltött adatbázist.
row_counts postgres >"$dumps/finance.rowcounts"

compose run --rm rclone sync garage:raw /backup/garage-raw

if ! compose run --rm restic cat config >/dev/null 2>&1; then
  compose run --rm restic init
fi

compose run --rm restic backup /backup/dumps /backup/garage-raw
compose run --rm restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
