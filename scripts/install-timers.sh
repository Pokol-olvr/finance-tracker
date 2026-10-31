#!/usr/bin/env bash
# Telepíti és bekapcsolja a napi mentés systemd timerét a repó tényleges helyével.
# Többször is futtatható, a repó áthelyezése után újra kell futtatni.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
units=$HOME/.config/systemd/user

mkdir -p "$units"
sed "s|^ExecStart=.*|ExecStart=$repo_root/scripts/backup.sh|" \
  "$repo_root/scripts/systemd/finance-backup.service" >"$units/finance-backup.service"
cp "$repo_root/scripts/systemd/finance-backup.timer" "$units/"

systemctl --user daemon-reload
systemctl --user enable --now finance-backup.timer
systemctl --user list-timers finance-backup.timer --no-pager
