#!/usr/bin/env bash
# Első beállítás a Metabase API-ján: két felhasználó és a finance adatforrás mb_reader-ként.
# A felhasználók adatai a .env-ből jönnek. Újrafuttatható, a meglévő részeket átugorja.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

: "${MB_ADMIN_EMAIL:?töltsd ki a .env MB_ADMIN_* mezőit}"
: "${MB_SECOND_EMAIL:?töltsd ki a .env MB_SECOND_* mezőit}"

api="http://${BIND_ADDRESS:-127.0.0.1}:${METABASE_PORT:-3000}/api"
session=

# POST a szabványos bemenet JSON-jével. Hibánál csak az okot írja ki: a Metabase
# teljes válasza a jelszót is visszaküldi.
post() {
  local response status
  response=$(curl -sS -w '\n%{http_code}' -H 'Content-Type: application/json' \
    ${session:+-H "X-Metabase-Session: $session"} -d @- "$api/$1")
  status=${response##*$'\n'}
  response=${response%$'\n'*}
  if [[ $status != 2* ]]; then
    echo "A /$1 hívás sikertelen ($status): $(jq -c '.errors // .message // "ismeretlen hiba"' <<<"$response")" >&2
    return 1
  fi
  echo "$response"
}

get() {
  curl -fsS -H "X-Metabase-Session: $session" "$api/$1"
}

properties=$(curl -fsS "$api/session/properties")

if [[ $(jq -r '."has-user-setup"' <<<"$properties") == true ]]; then
  session=$(
    jq -n --arg email "$MB_ADMIN_EMAIL" --arg password "$MB_ADMIN_PASSWORD" \
      '{username: $email, password: $password}' | post session | jq -r .id
  )
else
  session=$(
    jq -n \
      --arg token "$(jq -r '."setup-token"' <<<"$properties")" \
      --arg first "$MB_ADMIN_FIRST_NAME" --arg last "$MB_ADMIN_LAST_NAME" \
      --arg email "$MB_ADMIN_EMAIL" --arg password "$MB_ADMIN_PASSWORD" \
      '{token: $token,
        user: {first_name: $first, last_name: $last, email: $email, password: $password},
        prefs: {site_name: "Pénzügyi nyomkövető", site_locale: "hu", allow_tracking: false}}' |
      post setup | jq -r .id
  )
fi

if ! get user | jq -e --arg email "${MB_SECOND_EMAIL,,}" \
  '.data | any(.email | ascii_downcase == $email)' >/dev/null; then
  jq -n \
    --arg first "$MB_SECOND_FIRST_NAME" --arg last "$MB_SECOND_LAST_NAME" \
    --arg email "$MB_SECOND_EMAIL" --arg password "$MB_SECOND_PASSWORD" \
    '{first_name: $first, last_name: $last, email: $email, password: $password}' |
    post user >/dev/null
fi

if ! get database | jq -e '.data | any(.name == "Finance")' >/dev/null; then
  jq -n --arg password "$MB_READER_PASSWORD" \
    '{engine: "postgres", name: "Finance",
      details: {host: "postgres", port: 5432, dbname: "finance", user: "mb_reader",
                password: $password, ssl: false}}' |
    post database >/dev/null
fi

echo "A Metabase beállítva: két felhasználó és a Finance adatforrás."
