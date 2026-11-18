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

# A Pi adata (Vaultwarden, Authelia, a Pi .env-je) külön pillanatképbe, így a FIN-309 sem érinti.
# A kapcsolatot ez a gép nyitja; a Pi mentő kulcsa csak a friss mentést adja (scripts/pi/backup-user.sh).
pi_failed=false
if [[ -n ${PI_BACKUP_TARGET:-} ]]; then
  pi_key=${PI_BACKUP_KEY:-$HOME/.ssh/finance_pi_backup}
  rm -rf "$BACKUP_DIR/pi.new"
  mkdir -p "$BACKUP_DIR/pi.new"
  if ssh -i "$pi_key" -o BatchMode=yes -o IdentitiesOnly=yes "$PI_BACKUP_TARGET" |
    tar -C "$BACKUP_DIR/pi.new" -xf - &&
    [[ -s $BACKUP_DIR/pi.new/vaultwarden/db.sqlite3 && -s $BACKUP_DIR/pi.new/authelia/db.sqlite3 ]]; then
    rm -rf "$BACKUP_DIR/pi"
    mv "$BACKUP_DIR/pi.new" "$BACKUP_DIR/pi"
    compose run --rm restic backup --tag pi /backup/pi
    # A pi.env titkokat tart: nyersen nem marad a lemezen, csak a titkosított pillanatképben.
    rm -rf "$BACKUP_DIR/pi"
  else
    echo "A Pi mentése nem sikerült, az otthoni mentés megvan." >&2
    rm -rf "$BACKUP_DIR/pi.new"
    pi_failed=true
  fi
fi

compose run --rm restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
if $pi_failed; then
  exit 1
fi
