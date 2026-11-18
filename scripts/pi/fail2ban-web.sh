#!/usr/bin/env bash
# FIN-314 a Pi-n: fail2ban az Authelia és a Vaultwarden hibás belépéseire. Többször is futtatható.
#
#   sudo scripts/pi/fail2ban-web.sh <a feldolgozó gép Tailscale-címe>
#
# A két szolgáltatás a journalba ír (pi/docker-compose.yml, journald naplózó), a kliens címét a
# Caddy fejlécéből veszi. Ehhez a Pi Tailscale-e nem címezheti át a továbbított forgalmat
# (scripts/pi/tailscale-nosnat.sh), különben minden kérés a Docker-átjáró címéről jön.
# A tiltás a forward láncban van, mert a Docker a 80-as és a 443-as portot továbbítja, nem a Pi
# fogadja. A feldolgozó gép kivétel: a worker is ezen a címen húz a postaládából.
# Visszavonás: sudo rm /etc/fail2ban/jail.d/finance-web.local
#              /etc/fail2ban/filter.d/finance-authelia.conf /etc/fail2ban/filter.d/finance-vaultwarden.conf
#              && sudo systemctl restart fail2ban
set -euo pipefail

worker=${1:?a feldolgozó gép Tailscale-címe kell}

cat >/etc/fail2ban/filter.d/finance-authelia.conf <<'FILTER'
# Authelia 4.39: hibás jelszó vagy második faktor; a cím a remote_ip mezőben.
[Definition]
failregex = ^.*Unsuccessful (?:1FA|TOTP|Duo|WebAuthn|Passkey) authentication attempt by user .* remote_ip="?<HOST>"?(?:\s|$)
ignoreregex =
FILTER

cat >/etc/fail2ban/filter.d/finance-vaultwarden.conf <<'FILTER'
# Vaultwarden: hibás jelszó, hibás második faktor és hibás admin token.
[Definition]
failregex = ^.*Username or password is incorrect\. Try again\. IP: <HOST>(?:\.|\s|$)
            ^.*Invalid (?:TOTP code|two factor token).*IP: <HOST>(?:\.|\s|$)
            ^.*Invalid admin token\. IP: <HOST>(?:\.|\s|$)
ignoreregex =
FILTER

cat >/etc/fail2ban/jail.d/finance-web.local <<JAIL
# A Docker-konténerek forgalma a forward ponton megy át, ott kell tiltani; külön láncban, mert az
# sshd jail f2b-chain lánca az input ponton van, és egy lánc csak egy ponthoz köthető.
[authelia]
enabled = true
filter = finance-authelia
backend = systemd
journalmatch = CONTAINER_TAG=authelia
ignoreip = 127.0.0.1/8 ::1 $worker
port = http,https
banaction = nftables[type=multiport, chain_hook=forward, chain=f2b-docker]
maxretry = 5
findtime = 10m
bantime = 1h

[vaultwarden]
enabled = true
filter = finance-vaultwarden
backend = systemd
journalmatch = CONTAINER_TAG=vaultwarden
ignoreip = 127.0.0.1/8 ::1 $worker
port = http,https
banaction = nftables[type=multiport, chain_hook=forward, chain=f2b-docker]
maxretry = 5
findtime = 10m
bantime = 1h
JAIL
systemctl restart fail2ban
sleep 2
fail2ban-client status authelia
fail2ban-client status vaultwarden
echo "Kész: fail2ban az Authelia és a Vaultwarden belépéseire."
