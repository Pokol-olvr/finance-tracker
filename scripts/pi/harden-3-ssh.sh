#!/usr/bin/env bash
# FIN-313 3. lépés a Pi-n: SSH csak kulccsal, root nélkül, csak a megnevezett felhasználóknak.
#
#   sudo scripts/pi/harden-3-ssh.sh <rendszergazda> <korlátozott felhasználó>
#
# Előtte mindkét felhasználó kulcsos belépését ki kell próbálni. Az sshd az első értéket veszi,
# ezért a fájl neve 00-val kezdődik; újratöltés, nem újraindítás, a nyitott kapcsolatok megmaradnak.
# Visszavonás: sudo rm /etc/ssh/sshd_config.d/00-finance.conf && sudo systemctl reload ssh
set -euo pipefail

admin=${1:?a rendszergazda neve kell}
limited=${2:?a korlátozott felhasználó neve kell}
conf=/etc/ssh/sshd_config.d/00-finance.conf

cat >"$conf" <<SSHD
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
AllowUsers $admin $limited
MaxAuthTries 3
X11Forwarding no
AllowAgentForwarding no

# A korlátozott felhasználó nem építhet alagutat a Pi szolgáltatásaihoz.
Match User $limited
    AllowTcpForwarding no
    PermitTunnel no
SSHD
chmod 644 "$conf"

if ! sshd -t; then
  rm -f "$conf"
  echo "Hibás beállítás, visszavonva." >&2
  exit 1
fi
systemctl reload ssh
echo "Kész: SSH csak kulccsal."
