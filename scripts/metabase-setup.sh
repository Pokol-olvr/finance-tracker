#!/usr/bin/env bash
# Első beállítás a Metabase API-ján: két felhasználó és a finance adatforrás mb_reader-ként.
# A felhasználók adatai a .env-ből jönnek. Már beállított Metabase-nél nem csinál semmit.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

: "${MB_ADMIN_EMAIL:?töltsd ki a .env MB_ADMIN_* mezőit}"
: "${MB_SECOND_EMAIL:?töltsd ki a .env MB_SECOND_* mezőit}"

api="http://${BIND_ADDRESS:-127.0.0.1}:${METABASE_PORT:-3000}/api"

properties=$(curl -fsS "$api/session/properties")
if [[ $(jq -r '."has-user-setup"' <<<"$properties") == true ]]; then
  echo "A Metabase már be van állítva."
  exit 0
fi

session=$(
  jq -n \
    --arg token "$(jq -r '."setup-token"' <<<"$properties")" \
    --arg first "$MB_ADMIN_FIRST_NAME" --arg last "$MB_ADMIN_LAST_NAME" \
    --arg email "$MB_ADMIN_EMAIL" --arg password "$MB_ADMIN_PASSWORD" \
    '{token: $token,
      user: {first_name: $first, last_name: $last, email: $email, password: $password},
      prefs: {site_name: "Pénzügyi nyomkövető", site_locale: "hu", allow_tracking: false}}' |
    curl -fsS -H 'Content-Type: application/json' -d @- "$api/setup" | jq -r .id
)

post() {
  curl -fsS -H 'Content-Type: application/json' -H "X-Metabase-Session: $session" -d @- "$api/$1"
}

jq -n \
  --arg first "$MB_SECOND_FIRST_NAME" --arg last "$MB_SECOND_LAST_NAME" \
  --arg email "$MB_SECOND_EMAIL" --arg password "$MB_SECOND_PASSWORD" \
  '{first_name: $first, last_name: $last, email: $email, password: $password}' |
  post user >/dev/null

jq -n --arg password "$MB_READER_PASSWORD" \
  '{engine: "postgres", name: "Finance",
    details: {host: "postgres", port: 5432, dbname: "finance", user: "mb_reader",
              password: $password, ssl: false}}' |
  post database >/dev/null

echo "A Metabase beállítva: két felhasználó és a Finance adatforrás."
