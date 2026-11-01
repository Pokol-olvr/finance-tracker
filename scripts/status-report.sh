#!/usr/bin/env bash
# Elküldi a webappnak a stack állapotát; a finance-status.timer 15 másodpercenként futtatja.
# Egy kiesett szolgáltatás nem állíthatja meg a jelentést: ami nem elérhető, az üres marad.
set -euo pipefail
export PODMAN_COMPOSE_WARNING_LOGS=false
source "$(dirname "$0")/lib.sh"

status_url=${STATUS_URL:-http://127.0.0.1:${WEBAPP_PORT:-8000}}
data_dir=${DATA_DIR:-./data}

iso_time() {
  [[ -n $1 ]] || return 0
  date -d "$1" --iso-8601=seconds 2>/dev/null || true
}

job_report() {
  local name=$1 unit=$2 last next
  last=$(iso_time "$(systemctl --user show "$unit.timer" -p LastTriggerUSec --value)")
  next=$(iso_time "$(systemctl --user show "$unit.timer" -p NextElapseUSecRealtime --value)")
  jq -cn --arg name "$name" --arg last "$last" --arg next "$next" \
    --arg active "$(systemctl --user show "$unit.service" -p ActiveState --value)" \
    --arg result "$(systemctl --user show "$unit.service" -p Result --value)" \
    '{name: $name, active: $active, result: $result,
      last_run: (if $last == "" then null else $last end),
      next_run: (if $next == "" then null else $next end)}'
}

row_counts_json() {
  row_counts postgres 2>/dev/null |
    jq -Rcn '[inputs | split(" ") | {(.[0]): (.[1] | tonumber)}] | add // {}'
}

memory_bytes() {
  awk -v key="$1:" '$1 == key { printf "%.0f", $2 * 1024 }' /proc/meminfo
}

services=$(compose ps --format json | jq -cs 'map({name: .Service, state: .State, health: .Health})')
rows=$(row_counts_json) || rows='{}'
garage=$(compose exec -T garage /garage bucket info raw 2>/dev/null) || garage=
garage_objects=$(sed -n 's/^Objects: *//p' <<<"$garage")
garage_size=$(sed -n 's/^Size: *\([0-9.]* [A-Za-z]*\).*/\1/p' <<<"$garage")
jobs=$(
  job_report dbt finance-dbt
  job_report backup finance-backup
)
read -r disk_free disk_total < <(df -B1 --output=avail,size "$data_dir" | tail -1)
read -r load _ </proc/loadavg

report=$(jq -cn \
  --argjson services "$services" \
  --argjson row_counts "$rows" \
  --argjson jobs "$(jq -cs . <<<"$jobs")" \
  --arg garage_objects "$garage_objects" \
  --arg garage_size "$garage_size" \
  --argjson disk_free_bytes "$disk_free" \
  --argjson disk_total_bytes "$disk_total" \
  --argjson memory_available_bytes "$(memory_bytes MemAvailable)" \
  --argjson memory_total_bytes "$(memory_bytes MemTotal)" \
  --argjson load "$load" \
  '{services: $services, row_counts: $row_counts, jobs: $jobs,
    garage_objects: (if $garage_objects == "" then null else ($garage_objects | tonumber) end),
    garage_size: (if $garage_size == "" then null else $garage_size end),
    disk_free_bytes: $disk_free_bytes, disk_total_bytes: $disk_total_bytes,
    memory_available_bytes: $memory_available_bytes, memory_total_bytes: $memory_total_bytes,
    load: $load}')

# A token a curl bemenetén megy, így nem látszik a folyamatlistában.
printf 'Authorization: Bearer %s\n' "$WORKER_API_TOKEN" |
  curl -fsS -m 5 -o /dev/null -H @- -H 'Content-Type: application/json' \
    --data-binary "$report" "$status_url/inbox/status/host"
