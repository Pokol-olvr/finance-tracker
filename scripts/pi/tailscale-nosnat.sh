#!/usr/bin/env bash
# A Pi Tailscale-e ne címezze át a tailnetről a Docker felé továbbított forgalmat.
#
#   sudo scripts/pi/tailscale-nosnat.sh
#
# Alapból a Tailscale a tailscale0-ról továbbított csomagokat MASQUERADE-del átcímzi (ez a subnet
# routerhez kell, amit a Pi nem használ). Ilyenkor a Caddy, az Authelia és a Vaultwarden minden
# kérést a Docker-átjáró címéről lát, és a fail2ban nem tudja, kit tiltson. A Pi-hole natívan fut,
# ezt nem érinti. Élesítéskor 5 perces önvisszavonó időzítő indul; ha minden működik:
#   sudo systemctl stop nosnat-rollback.timer
# Visszavonás: sudo tailscale set --snat-subnet-routes=true
set -euo pipefail

systemd-run --unit=nosnat-rollback --on-active=300 /usr/bin/tailscale set --snat-subnet-routes=true
tailscale set --snat-subnet-routes=false
iptables -t nat -S ts-postrouting
echo "Kész. Próba után: sudo systemctl stop nosnat-rollback.timer"
