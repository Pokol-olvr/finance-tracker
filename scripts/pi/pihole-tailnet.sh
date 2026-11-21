#!/usr/bin/env bash
# FIN-315 a Pi-n: a Pi-hole v6 webszervere csak a helyi címen figyel, így a Tailscale-cím 80-as és
# 443-as portja a Caddyé; a saját domain nevei helyi rekordként a Pi Tailscale-címére mutatnak.
# A Pi maga nem a Tailscale DNS-ét használja, hogy a tailscaled kiesése ne vigye el a névfeloldását.
#
#   sudo scripts/pi/pihole-tailnet.sh <a Pi helyi címe> <név> [név...]
#   pl. sudo scripts/pi/pihole-tailnet.sh 192.168.1.10 penzugy.example.hu auth.penzugy.example.hu
#
# A meglévő helyi rekordok megmaradnak; a régi értékeket a kimenet elején kiírja. Visszavonás:
#   sudo pihole-FTL --config webserver.port '<régi érték>'
#   sudo pihole-FTL --config dns.hosts '<régi érték>'
#   sudo tailscale set --accept-dns=true
set -euo pipefail

lan_ip=${1:?a Pi helyi címe kell}
shift
[[ $# -gt 0 ]] || { echo "Legalább egy név kell." >&2; exit 2; }
ts_ip=$(tailscale ip -4)

echo "== visszaállításhoz, a régi értékek"
echo "webserver.port: $(pihole-FTL --config webserver.port)"
old_hosts=$(pihole-FTL --config dns.hosts)
echo "dns.hosts: $old_hosts"

new_hosts=$(python3 - "$ts_ip" "$old_hosts" "$@" <<'PY'
import json, sys
ip, current, names = sys.argv[1], sys.argv[2], sys.argv[3:]
try:
    hosts = json.loads(current)
except json.JSONDecodeError:
    hosts = current.strip().strip("[]").split(",")
hosts = [h.strip().strip('"') for h in hosts if h.strip().strip('"')]
kept = [h for h in hosts if h.split()[-1] not in names]
print(json.dumps(kept + [f"{ip} {name}" for name in names]))
PY
)

pihole-FTL --config webserver.port "$lan_ip:80o,$lan_ip:443os"
pihole-FTL --config dns.hosts "$new_hosts"
# Üres resolv.conf mellett a rendszer a 127.0.0.1-et, vagyis a saját Pi-hole-t kérdezi.
tailscale set --accept-dns=false
sleep 3

echo "== új értékek"
echo "webserver.port: $(pihole-FTL --config webserver.port)"
echo "dns.hosts: $(pihole-FTL --config dns.hosts)"
getent hosts "$1"
