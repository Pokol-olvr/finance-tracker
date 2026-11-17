#!/usr/bin/env bash
# FIN-313 4. lépés véglegesítése: leállítja az 5 perces visszavonó időzítőt.
set -euo pipefail
systemctl stop ufw-visszavonas.timer
systemctl enable ufw >/dev/null
echo "Kész: a tűzfal végleges, újraindítás után is él."
