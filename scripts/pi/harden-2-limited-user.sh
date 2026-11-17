#!/usr/bin/env bash
# FIN-313 2. lépés a Pi-n: korlátozott felhasználó. SSH-val, kulccsal belép és olvashat, de nincs
# sudo, nincs docker csoport (az rootjogot adna), és jelszava sincs. Többször is futtatható.
#
#   sudo scripts/pi/harden-2-limited-user.sh <felhasználó> <a rendszergazda neve> '<nyilvános kulcs>'
#
# A kulcs a korlátozott felhasználó saját kulcsa legyen: a rendszergazdáéval ugyanaz a kulcs
# a rendszergazdaként is beléptetne.
# Visszavonás: sudo userdel -r <felhasználó>
set -euo pipefail

user=${1:?a korlátozott felhasználó neve kell}
admin=${2:?a rendszergazda neve kell}
key=${3:?a korlátozott felhasználó nyilvános kulcsa kell}

id "$user" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash --comment "Csak olvasas" "$user"
passwd --lock "$user" >/dev/null
for group in sudo docker adm lpadmin netdev; do
  gpasswd --delete "$user" "$group" >/dev/null 2>&1 || true
done

install -d -m 700 -o "$user" -g "$user" "/home/$user/.ssh"
printf '%s\n' "$key" >"/home/$user/.ssh/authorized_keys"
chown "$user:$user" "/home/$user/.ssh/authorized_keys"
chmod 600 "/home/$user/.ssh/authorized_keys"

# A rendszergazda mappáját a korlátozott felhasználó ne lássa.
chmod 750 "/home/$admin"
echo "Kész: $(id "$user")"
