#!/usr/bin/env bash
# Telepíti és bekapcsolja a systemd timereket a repó tényleges helyével.
# Többször is futtatható, a repó áthelyezése után újra kell futtatni.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
units=$HOME/.config/systemd/user

mkdir -p "$units"
for name in finance-dbt finance-backup; do
  sed "s|^ExecStart=%h/finance-tracker/|ExecStart=$repo_root/|" \
    "$repo_root/scripts/systemd/$name.service" >"$units/$name.service"
  cp "$repo_root/scripts/systemd/$name.timer" "$units/"
done

systemctl --user daemon-reload
systemctl --user enable --now finance-dbt.timer finance-backup.timer
systemctl --user list-timers 'finance-*' --no-pager
