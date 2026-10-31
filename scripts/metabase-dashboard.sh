#!/usr/bin/env bash
# Létrehozza az Áttekintés dashboardot a gold táblákból. Ha már van, nem nyúl hozzá.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
source "$REPO_ROOT/scripts/metabase-lib.sh"

dashboard_name="Áttekintés"

metabase_login

database_id=$(get database | jq -r '.data[] | select(.name == "Finance") | .id')
if [[ -z $database_id ]]; then
  echo "Nincs Finance adatforrás, előbb futtasd a scripts/metabase-setup.sh-t." >&2
  exit 1
fi

post "database/$database_id/sync_schema" <<<'{}' >/dev/null

if get dashboard | jq -e --arg name "$dashboard_name" 'any(.[]; .name == $name)' >/dev/null; then
  echo "Az $dashboard_name dashboard már létezik."
  exit 0
fi

# Minden kártya ebből indul, így a fizető fél szűrője mindenhol ugyanúgy hat.
monthly="with monthly as (
  select month, sum(income) as income, sum(expense) as expense
  from gold.monthly_cash_flow
  where true [[and payer = {{payer}}]]
  group by month
), this_month as (
  select date_trunc('month', current_date)::date as month
)"

rate="round((income - expense) / nullif(income, 0) * 100, 1)"

scalar() {
  echo "$monthly
select $1 from monthly where month = (select month from this_month)"
}

comparison="$monthly, periods as (
  select 1 as position, 'Ez a hónap' as period, income, expense
  from monthly where month = (select month from this_month)
  union all
  select 2, 'Előző hónap', income, expense
  from monthly where month = (select month - interval '1 month' from this_month)
  union all
  select 3, 'Előző 3 lezárt hónap átlaga', avg(income), avg(expense)
  from monthly
  where month >= (select month - interval '3 months' from this_month)
    and month < (select month from this_month)
)
select
  period as \"Időszak\",
  round(income, 0) as \"Bevétel\",
  round(expense, 0) as \"Kiadás\",
  round(income - expense, 0) as \"Egyenleg\",
  $rate as \"Megtakarítási ráta (%)\"
from periods
order by position"

categories="select category as \"Kategória\", sum(expense) as \"Kiadás\"
from gold.category_month
where month = date_trunc('month', current_date)::date [[and payer = {{payer}}]]
group by category
order by 2 desc"

create_card() {
  jq -n --arg name "$1" --arg display "$2" --arg query "$3" --argjson database "$database_id" \
    '{name: $name, display: $display, visualization_settings: {},
      dataset_query: {database: $database, type: "native", native: {query: $query,
        "template-tags": {payer: {id: "payer", name: "payer", "display-name": "Fizető fél", type: "text"}}}}}' |
    post card | jq -r .id
}

# Név, megjelenítés, SQL, oszlop, sor, szélesség, magasság
dashcards='[]'
add_card() {
  local card_id
  card_id=$(create_card "$1" "$2" "$3")
  dashcards=$(jq --argjson card "$card_id" --argjson col "$4" --argjson row "$5" \
    --argjson width "$6" --argjson height "$7" \
    '. + [{id: (-1 - length), card_id: $card, col: $col, row: $row, size_x: $width, size_y: $height,
           parameter_mappings: [{parameter_id: "payer", card_id: $card,
                                 target: ["variable", ["template-tag", "payer"]]}]}]' <<<"$dashcards")
}

add_card "Bevétel ezen a hónapon" scalar "$(scalar 'income')" 0 0 6 3
add_card "Kiadás ezen a hónapon" scalar "$(scalar 'expense')" 6 0 6 3
add_card "Egyenleg ezen a hónapon" scalar "$(scalar 'income - expense')" 12 0 6 3
add_card "Megtakarítási ráta ezen a hónapon (%)" scalar "$(scalar "$rate")" 18 0 6 3
add_card "Összehasonlítás" table "$comparison" 0 3 14 6
add_card "Kiadás kategóriánként ezen a hónapon" bar "$categories" 14 3 10 6

dashboard_id=$(jq -n --arg name "$dashboard_name" '{name: $name}' | post dashboard | jq -r .id)

members=${HOUSEHOLD_MEMBERS:-person_a,person_b}
jq -n --argjson cards "$dashcards" --arg members "shared,$members" \
  '{dashcards: $cards,
    parameters: [{id: "payer", name: "Fizető fél", slug: "payer", type: "string/=",
                  sectionId: "string", values_source_type: "static-list",
                  values_source_config: {values: ($members | split(","))}}]}' |
  post "dashboard/$dashboard_id" PUT >/dev/null

echo "Elkészült az $dashboard_name dashboard: http://${BIND_ADDRESS:-127.0.0.1}:${METABASE_PORT:-3000}/dashboard/$dashboard_id"
