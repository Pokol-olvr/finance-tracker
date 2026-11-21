#!/usr/bin/env bash
# A Vaultwarden regisztrációjának ideiglenes megnyitása egy új fiókhoz; magától be is zárul.
#
#   sudo scripts/pi/vault-signups.sh open [perc]   # alapból 30 perc
#   sudo scripts/pi/vault-signups.sh close
#
# Levélküldés nincs, ezért meghívó helyett a regisztráció nyílik meg rövid időre. A Vaultwarden
# csak a tailnetről érhető el, de a nyitott ablakban bárki regisztrálhat, aki a tailneten van;
# ezért egy időzítő a megadott idő után akkor is bezárja, ha a close elmarad.
set -euo pipefail

repo=$(cd "$(dirname "$0")/../.." && pwd)
env_file=$repo/pi/.env
unit=vault-signups-close

set_signups() {
  sed -i "s/^VAULT_SIGNUPS_ALLOWED=.*/VAULT_SIGNUPS_ALLOWED=$1/" "$env_file"
  grep -qx "VAULT_SIGNUPS_ALLOWED=$1" "$env_file"
  docker compose -f "$repo/pi/docker-compose.yml" up -d vaultwarden
}

stop_timer() {
  systemctl stop "$unit.timer" 2>/dev/null || true
  systemctl reset-failed "$unit.service" 2>/dev/null || true
}

case ${1:-} in
  open)
    minutes=${2:-30}
    stop_timer
    set_signups true
    systemd-run --quiet --unit="$unit" --on-active="${minutes}m" "$repo/scripts/pi/vault-signups.sh" close
    echo "A regisztráció nyitva; $minutes perc múlva magától bezárul (vagy: sudo $0 close)."
    ;;
  close)
    stop_timer
    set_signups false
    echo "A regisztráció lezárva."
    ;;
  *)
    echo "Használat: sudo $0 open [perc] | close" >&2
    exit 2
    ;;
esac
