#!/usr/bin/env bash
# FIN-313 4. lépés a Pi-n: tűzfal. A Pi a háztartás DNS-szervere, ezért élesítéskor egy 5 perces
# időzítő indul, amely magától kikapcsolja a tűzfalat. Ellenőrzés után a harden-4-finalize.sh
# állítja le. Visszavonás bármikor: sudo ufw disable
#
#   sudo scripts/pi/harden-4-ufw.sh <helyi hálózat, pl. 192.168.0.0/24>
#
# A Docker által közzétett portokra a tűzfal nem vonatkozik: a konténer csak a Tailscale-címre
# köthet portot.
set -euo pipefail

lan=${1:?a helyi hálózat kell, pl. 192.168.0.0/24}

apt-get install -y ufw
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing

# Helyi hálózat: DNS, idő (a Pi-hole NTP-szervere), SSH, a Pi-hole felülete, mDNS és a Beszel hub.
ufw allow from "$lan" to any port 53 comment "DNS LAN"
ufw allow from "$lan" to any port 123 proto udp comment "NTP LAN"
ufw allow from "$lan" to any port 22 proto tcp comment "SSH LAN"
ufw allow from "$lan" to any port 80,443 proto tcp comment "Pi-hole LAN"
ufw allow from "$lan" to any port 5353 proto udp comment "mDNS LAN"
ufw allow from "$lan" to any port 8090 proto tcp comment "Beszel LAN"

# Tailnet: DNS, SSH és a Caddy; a Tailscale közvetlen kapcsolataihoz a 41641/udp.
ufw allow in on tailscale0 to any port 53 comment "DNS tailnet"
ufw allow in on tailscale0 to any port 22 proto tcp comment "SSH tailnet"
ufw allow in on tailscale0 to any port 80,443 proto tcp comment "Caddy tailnet"
ufw allow 41641/udp comment "Tailscale"

systemctl stop ufw-visszavonas.timer 2>/dev/null || true
systemd-run --unit=ufw-visszavonas --on-active=300 /usr/sbin/ufw disable >/dev/null
ufw --force enable
ufw status numbered
echo "A tűzfal él. 5 percen belül véglegesíteni kell, különben magától kikapcsol."
