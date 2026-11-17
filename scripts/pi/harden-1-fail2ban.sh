#!/usr/bin/env bash
# FIN-313 1. lépés a Pi-n: fail2ban az SSH-ra és automatikus biztonsági frissítés. Többször is futtatható.
#
#   sudo scripts/pi/harden-1-fail2ban.sh <a feldolgozó gép helyi IP-címe>
#
# Kívülről semmi nem érhető el, ezért a helyi hálózat és a tailnet nem kivétel: csak a Pi saját
# maga és a feldolgozó gép, hogy munka közben ne zárjuk ki magunkat.
# Visszavonás: sudo rm /etc/fail2ban/jail.d/finance.local /etc/apt/apt.conf.d/52finance-unattended
#              && sudo systemctl restart fail2ban
set -euo pipefail

trusted=${1:?a feldolgozó gép helyi IP-címe kell}

apt-get update
apt-get install -y fail2ban unattended-upgrades python3-systemd

cat >/etc/fail2ban/jail.d/finance.local <<JAIL
[DEFAULT]
ignoreip = 127.0.0.1/8 ::1 $trusted
bantime = 1h
findtime = 10m
maxretry = 5
backend = systemd

# A Debian 13 OpenSSH-ja a belépést az sshd-session folyamatban naplózza, a fail2ban 1.1 alap
# szűrője viszont csak az sshd folyamatot figyeli; a kulcs nélküli próbát az aggressive mód számolja.
[sshd]
enabled = true
mode = aggressive
journalmatch = _SYSTEMD_UNIT=ssh.service
JAIL
systemctl enable fail2ban
systemctl restart fail2ban
sleep 2
fail2ban-client status sshd

# Csak a Debian biztonsági frissítései, újraindítás nélkül, mert a Pi a háztartás DNS-szervere.
echo unattended-upgrades unattended-upgrades/enable_auto_updates boolean true | debconf-set-selections
dpkg-reconfigure -f noninteractive unattended-upgrades
cat >/etc/apt/apt.conf.d/52finance-unattended <<'UPG'
Unattended-Upgrade::Automatic-Reboot "false";
UPG
systemctl enable --now unattended-upgrades
echo "Kész: fail2ban és automatikus biztonsági frissítés."
