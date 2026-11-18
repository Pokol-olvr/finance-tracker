#!/usr/bin/env bash
# FIN-314 a Pi-n: mentő felhasználó, amelynek a kulcsa csak a friss mentést kérheti le.
#
#   sudo scripts/pi/backup-user.sh '<a feldolgozó gép mentőkulcsának publikus része>'
#
# A mentes felhasználónak nincs jelszava és nincs shellje: a kulcsa kényszerített paranccsal fut
# (restrict, command=...), így belépve csak a finance-pi-snapshot kimenetét kapja, alagutat nem
# építhet. A sudo csak ezt az egy parancsot engedi neki. Az SSH-ban külön fájl veszi fel az
# engedélyezett felhasználók közé, a meglévő beállítás nem változik.
# Visszavonás: sudo rm /etc/ssh/sshd_config.d/01-finance-backup.conf /etc/sudoers.d/finance-backup
#              /usr/local/sbin/finance-pi-snapshot && sudo systemctl reload ssh && sudo userdel -r mentes
set -euo pipefail

key=${1:?a mentőkulcs publikus része kell}
[[ $key == ssh-ed25519\ * ]] || {
  echo "ed25519 publikus kulcs kell (ssh-ed25519 ...)." >&2
  exit 1
}
repo=$(cd "$(dirname "$0")/../.." && pwd)
user=mentes

# A parancs a repó helyével együtt kerül a rendszerbe, root tulajdonában.
sed "s|^repo=\${FINANCE_REPO:?a repó helye}$|repo=$repo|" "$repo/scripts/pi/backup-snapshot.sh" \
  >/usr/local/sbin/finance-pi-snapshot
chown root:root /usr/local/sbin/finance-pi-snapshot
chmod 755 /usr/local/sbin/finance-pi-snapshot
grep -q "^repo=$repo$" /usr/local/sbin/finance-pi-snapshot

id "$user" >/dev/null 2>&1 || useradd --system --create-home --shell /bin/sh "$user"
passwd -l "$user" >/dev/null

home=$(getent passwd "$user" | cut -d: -f6)
install -d -m 700 -o "$user" -g "$user" "$home/.ssh"
printf 'restrict,command="sudo -n /usr/local/sbin/finance-pi-snapshot" %s\n' "$key" >"$home/.ssh/authorized_keys"
chown "$user:$user" "$home/.ssh/authorized_keys"
chmod 600 "$home/.ssh/authorized_keys"

sudoers=/etc/sudoers.d/finance-backup
echo "$user ALL=(root) NOPASSWD: /usr/local/sbin/finance-pi-snapshot" >"$sudoers.tmp"
chmod 440 "$sudoers.tmp"
visudo -cf "$sudoers.tmp" >/dev/null
mv "$sudoers.tmp" "$sudoers"

conf=/etc/ssh/sshd_config.d/01-finance-backup.conf
cat >"$conf" <<SSHD
# A mentő felhasználó; az AllowUsers sorai összeadódnak a 00-finance.conf soraival.
AllowUsers $user
Match User $user
    AllowTcpForwarding no
    PermitTunnel no
    X11Forwarding no
    PermitTTY no
SSHD
chmod 644 "$conf"
if ! sshd -t; then
  rm -f "$conf"
  echo "Hibás SSH-beállítás, visszavonva." >&2
  exit 1
fi
systemctl reload ssh
sshd -T | grep -i '^allowusers'
echo "Kész: a $user kulcsa csak a mentést kérheti le."
