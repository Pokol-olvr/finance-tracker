# A Metabase API közös része; a lib.sh után töltődik be, önállóan nem fut.

api="http://${BIND_ADDRESS:-127.0.0.1}:${METABASE_PORT:-3000}/api"
session=

# POST a szabványos bemenet JSON-jével. Hibánál csak az okot írja ki: a Metabase
# teljes válasza a jelszót is visszaküldi.
post() {
  local response status
  response=$(curl -sS -w '\n%{http_code}' -X "${2:-POST}" -H 'Content-Type: application/json' \
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

metabase_login() {
  session=$(
    jq -n --arg email "$MB_ADMIN_EMAIL" --arg password "$MB_ADMIN_PASSWORD" \
      '{username: $email, password: $password}' | post session | jq -r .id
  )
}
