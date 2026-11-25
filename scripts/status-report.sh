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
# A backup.sh a sikeres Pi-mentés idejét írja ide; Pi nélkül nincs ilyen fájl.
pi_backup_at=$(iso_time "$(cat "$BACKUP_DIR/pi-backup-ok" 2>/dev/null || true)")
jobs=$(
  job_report dbt finance-dbt
  job_report backup finance-backup |
    jq -c --arg pi "$pi_backup_at" 'if $pi == "" then . else . + {pi_backup_at: $pi} end'
)
read -r disk_free disk_total < <(df -B1 --output=avail,size "$data_dir" | tail -1)

# Magonkénti CPU-terhelés egy másodperces mintából; a /proc/stat a gép indulása óta számol.
cpu_sample() { grep '^cpu' /proc/stat; }
cpu_before=$(cpu_sample)
sleep 1
cpu_after=$(cpu_sample)
cpu_model=$(sed -n 's/^model name[[:space:]]*:[[:space:]]*//p' /proc/cpuinfo | head -1)
cpu=$(paste <(echo "$cpu_before") <(echo "$cpu_after") | awk '{
    n = NF / 2; total = 0; idle = ($(n + 5) + $(n + 6)) - ($5 + $6)
    for (i = 2; i <= n; i++) total += $(n + i) - $i
    printf "%s %.1f" "\n", $1, (total > 0 ? (1 - idle / total) * 100 : 0)
  }' | jq -Rcn --arg model "$cpu_model" '[inputs | split(" ")] | {
    model: (if $model == "" then null else $model end),
    percent: (.[0][1] | tonumber),
    cores: (.[1:] | map(.[1] | tonumber))}')

# WSL-ben az nvidia-smi a /usr/lib/wsl/lib alatt van, ami a systemd timer PATH-jában nincs benne.
[[ -d /usr/lib/wsl/lib ]] && PATH=$PATH:/usr/lib/wsl/lib

# GPU csak ott van, ahol az nvidia-smi fut; a pillanatnyi kép, a 15 másodperc közötti csúcs elveszhet.
gpu=null
if command -v nvidia-smi >/dev/null &&
  line=$(nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw     --format=csv,noheader,nounits 2>/dev/null | head -1) && [[ -n $line ]]; then
  gpu=$(jq -cn --arg line "$line" '$line | split(", ") | map(gsub("^ +| +$"; "")) | {
    name: .[0],
    utilization_percent: (.[1] | tonumber? // null),
    memory_used_bytes: ((.[2] | tonumber? // 0) * 1048576 | floor),
    memory_total_bytes: ((.[3] | tonumber? // 0) * 1048576 | floor),
    temperature_c: (.[4] | tonumber? // null),
    power_w: (.[5] | tonumber? // null)}')
fi

# Az Ollama konténer CPU-használata, 100% egy teljes mag; a Docker és a Podman is így adja.
engine=${COMPOSE%% *}
ollama_id=$(compose ps -q ollama 2>/dev/null) || ollama_id=
ollama_cpu=
if [[ -n $ollama_id ]]; then
  ollama_cpu=$($engine stats --no-stream --format '{{.CPUPerc}}' "$ollama_id" 2>/dev/null | tr -d '% ') || ollama_cpu=
fi
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
  --argjson gpu "$gpu" \
  --arg ollama_cpu "$ollama_cpu" \
  --argjson cpu "$cpu" \
  --argjson swap_total_bytes "$(memory_bytes SwapTotal)" \
  --argjson swap_free_bytes "$(memory_bytes SwapFree)" \
  '{services: $services, row_counts: $row_counts, jobs: $jobs,
    garage_objects: (if $garage_objects == "" then null else ($garage_objects | tonumber) end),
    garage_size: (if $garage_size == "" then null else $garage_size end),
    disk_free_bytes: $disk_free_bytes, disk_total_bytes: $disk_total_bytes,
    memory_available_bytes: $memory_available_bytes, memory_total_bytes: $memory_total_bytes,
    load: $load, gpu: $gpu, cpu: $cpu,
    swap_total_bytes: $swap_total_bytes, swap_used_bytes: ($swap_total_bytes - $swap_free_bytes),
    ollama_cpu_percent: ($ollama_cpu | tonumber? // null)}')

# A token a curl bemenetén megy, így nem látszik a folyamatlistában.
printf 'Authorization: Bearer %s\n' "$WORKER_API_TOKEN" |
  curl -fsS -m 5 -o /dev/null -H @- -H 'Content-Type: application/json' \
    --data-binary "$report" "$status_url/inbox/status/host"
