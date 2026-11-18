#!/usr/bin/env bash
# Felvesz vagy lecserél egy Authelia-felhasználót a Pi-n. A jelszót az Authelia kéri be, így az
# sem a parancssorban, sem a shell előzményeiben nem jelenik meg; a fájlba csak a hash kerül.
#
#   scripts/authelia-user.sh person_a
set -euo pipefail

[[ $# -eq 1 ]] || {
  echo "Használat: $0 <felhasználó, a HOUSEHOLD_MEMBERS egyik kódja>" >&2
  exit 2
}
user=$1
[[ $user =~ ^[a-z0-9_]+$ ]] || {
  echo "A felhasználónév kisbetű, szám és aláhúzás lehet." >&2
  exit 1
}

repo_root=$(cd "$(dirname "$0")/.." && pwd)
data_dir=$(grep -s '^DATA_DIR=' "$repo_root/pi/.env" | cut -d= -f2-)
data_dir=${data_dir:-$repo_root/pi/data}
users=$data_dir/authelia/users_database.yml
image=$(sed -n 's/^ *image: *\(docker.io\/authelia\/authelia:.*\)$/\1/p' "$repo_root/pi/docker-compose.yml")

# A kimenet a terminálra is kimegy, különben a jelszókérdés nem látszik; a hash nem titok.
echo "$user jelszava, utána a megerősítés:"
digest=$(docker run --rm -it "$image" authelia crypto hash generate argon2 |
  tee /dev/tty | tr -d '\r' | sed -n 's/^Digest: //p')
[[ $digest == \$argon2* ]] || {
  echo "A hash nem készült el." >&2
  exit 1
}

mkdir -p "$(dirname "$users")"
umask 077
[[ -f $users ]] || echo "users:" >"$users"

# A régi bejegyzés a felhasználó soráig és az utána álló behúzott sorokig kikerül.
awk -v user="  $user:" '
  $0 == user { skip = 1; next }
  skip && /^    / { next }
  { skip = 0; print }
' "$users" >"$users.new"
cat >>"$users.new" <<EOF
  $user:
    displayname: "$user"
    password: "$digest"
EOF
mv "$users.new" "$users"

echo "Kész: $user. A TOTP-t az első belépéskor kell beállítani; a megerősítő kód a"
echo "$data_dir/authelia/notification.txt fájlba kerül."
