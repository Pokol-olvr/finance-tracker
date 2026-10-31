---
projekt: Pénzügyi nyomkövető
sprint: S2
kezdes: 2026-11-16
vege: 2026-11-29
story_pont: 11
tags: [penzugy, sprint]
---

# Sprint 2

Vissza: [[Fejlesztési terv]]

## Sprint cél

**A kézzel felvitt bevétel és kiadás a bronzból a silveren és a golden át eljut a Metabase Áttekintés dashboardjára.** A sprint 2026-11-16 és 2026-11-29 között tart, 11 story ponttal.

| Kulcs | Jegy | SP | Függ tőle |
| --- | --- | --- | --- |
| FIN-202 | dbt projekt és első silver | 3 | FIN-201, FIN-105 |
| FIN-203 | Kézi bejegyzés API a bronzba | 3 | FIN-201 |
| FIN-204 | Gold: havi cash-flow és kategória-hónap | 3 | FIN-202 |
| FIN-205 | Metabase Áttekintés dashboard | 2 | FIN-203, FIN-204 |

Javasolt sorrend: FIN-202, FIN-203, FIN-204, végül a FIN-205. A FIN-204 kitalált adaton tesztel, ezért nem vár a FIN-203-ra, de a dashboardhoz már kell a felvitt adat.

**Mock adat:** a sprintben minden helyben fut, és csak kitalált adat kerül a rendszerbe, ezért a DoD valós adatos próbája most nem értelmezhető. A bronzból semmi nem törölhető, így az első éles használat előtt a `finance` adatbázis üresen újraépül.

**Hibás adat:** a kézi bejegyzés végleges, a korrekciós tábla csak a FIN-406-tal, a 6. sprintben jön. A szándékosan hibás adatot adó próbák eldobható adatbázisban futnak, nem a helyi stacken.

## FIN-202 dbt projekt és első silver · 3 SP

**Story:** adatgazdaként azt akarom, hogy a silver réteg egy paranccsal, tesztekkel együtt épüljön fel a bronzból, hogy minden szám visszavezethető legyen a nyers adatra.

**Részfeladatok**

- [x] `dbt/Dockerfile` rögzített verziókkal: `python:3.13.18-slim`, `dbt-core==1.12.6`, `dbt-postgres==1.11.0` 📅 2026-11-29
- [x] `dbt` szolgáltatás a Compose-ban a `tools` profilban, `dbt_runner`-ként, a `DBT_RUNNER_PASSWORD` változóval 📅 2026-11-29
- [x] `dbt_project.yml` és `profiles.yml`, jelszó csak `env_var`-ból 📅 2026-11-29
- [x] `macros/generate_schema_name.sql`, hogy a modellek a `silver` és `gold` sémába kerüljenek, ne `silver_silver` névre ([forrás](https://docs.getdbt.com/docs/build/custom-schemas)) 📅 2026-11-29
- [x] Források: a három bronz tábla `sources.yml`-ben 📅 2026-11-29
- [x] `dbt/seeds/categories.csv` az alap kategóriákkal: élelmiszer, háztartás, lakbér, közlekedés, szórakozás, egészség 📅 2026-11-29
- [x] `silver.transactions` a `manual_entry` táblából (lásd lent) 📅 2026-11-29
- [x] Tesztek: egyedi és kitöltött `transaction_id`, a `kind` megengedett értékei, `amount > 0`, kiadás kategóriája a seedben szerepel 📅 2026-11-29
- [x] A CI `dbt build` helyőrzője helyett valódi lépés a migrációk után 📅 2026-11-29
- [x] Éjszakai `dbt build`: `finance-dbt.timer` 03:00-kor, hogy a 03:30-as mentés a friss silvert és goldot vigye 📅 2026-11-29
- [x] README: a `dbt build` futtatása 📅 2026-11-29

**Elfogadási feltételek**

- [x] A `dbt build` üres bronzon és adattal is zöld, és a tesztek futnak
- [x] A `silver.transactions` a `silver` sémában jön létre, a modellek nem hoznak létre új sémát
- [x] Eldobható adatbázisban egy `amount = -1` sor piros `dbt build`-et ad
- [ ] Hibás modellnél a CI piros
- [ ] Az éjszakai futás után a `silver.transactions` frissült

**Silver tábla: `silver.transactions`**

Egységes tranzakció: a későbbi források (blokk, bérpapír, kivonat) ugyanide érkeznek.

| Mező | Forrás | Megjegyzés |
| --- | --- | --- |
| `transaction_id` | `id` | |
| `source` | `'manual'` | Később `receipt`, `payslip`, `statement` |
| `kind` | `kind` | `expense`, `income`, `transfer` |
| `amount` | `amount` | Mindig pozitív, az irányt a `kind` adja |
| `currency` | `currency` | |
| `occurred_on` | `occurred_on` | A vásárlás napja, nem a rögzítésé |
| `purchased_by` | `purchased_by` | Aki vásárolt, mindig személy |
| `payer` | `payer` | Aki fizetett, lehet a közös kártya is |
| `category` | `tags[1]` | Csak kiadásnál, a FIN-203 pontosan egyet enged |
| `entered_by` | `entered_by` | |
| `note` | `note` | |

**Minta: a séma nevének felülírása és a modell**

```sql
-- macros/generate_schema_name.sql
{% macro generate_schema_name(custom_schema_name, node) -%}
  {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}
```

```sql
-- models/silver/transactions.sql
select
  id as transaction_id,
  'manual' as source,
  kind,
  amount,
  currency,
  occurred_on,
  payer,
  tags[1] as category,
  entered_by,
  note
from {{ source('bronze', 'manual_entry') }}
```

## FIN-203 Kézi bejegyzés API a bronzba · 3 SP

**Story:** felhasználóként blokk nélküli kiadást és bevételt akarok rögzíteni, hogy a kép már a blokkbeolvasás előtt teljes legyen.

**Részfeladatok**

- [x] Migráció: nem kötelező `purchased_by` mező a `raw_document` és a `manual_entry` táblába 📅 2026-11-29
- [x] `webapp/` FastAPI alkalmazás rögzített verziókkal: `fastapi==0.162.0`, `uvicorn==0.54.0`, `psycopg==3.3.6`, `pydantic==2.14.2` 📅 2026-11-29
- [x] `webapp/Dockerfile` és `webapp` szolgáltatás a Compose-ban, `app_writer`-ként, `restart: unless-stopped` 📅 2026-11-29
- [x] Port csak helyben: `127.0.0.1:${WEBAPP_PORT:-8000}`; belépés nincs, ezért a hálózaton nem látszhat a FIN-303-ig 📅 2026-11-29
- [x] `GET /health` és `POST /entries` 📅 2026-11-29
- [x] Validálás a lenti szabályok szerint; pénzösszeg `Decimal`, float soha 📅 2026-11-29
- [x] Ismételt küldés elleni védelem: az `id`-t a kliens adja, az írás `on conflict (id) do nothing` 📅 2026-11-29
- [x] Az írás egyetlen modulban legyen (`webapp/app/store.py`), hogy a Pi-re költözéskor cserélhető maradjon ([[0005-monorepo-es-atmeneti-otthoni-webapp|ADR 0005]]) 📅 2026-11-29
- [x] `HOUSEHOLD_MEMBERS` változó a `.env.example`-ben: a két személy kódja; a nevek nem kerülnek a repóba 📅 2026-11-29
- [x] Mock bejegyzések az API-n át, kitalált összegekkel, `entered_by = mock` értékkel 📅 2026-11-29
- [x] pytest-tesztek a validálásra és a bronz írásra, CI-lépéssel 📅 2026-11-29
- [x] README: a végpont használata egy `curl` példával, kitalált adattal 📅 2026-11-29

**Elfogadási feltételek**

- [x] A felvitt tétel a következő `dbt build` után megjelenik a `silver.transactions` táblában
- [x] Érvénytelen kérésre 422 jön, és a bronz nem változik
- [x] Ugyanaz az `id` kétszer elküldve egy sort hoz létre
- [x] Módosító és törlő végpont nincs
- [x] A webapp portja a gazdagépen csak a `127.0.0.1` címen figyel

**Validálási szabályok**

| Mező | Szabály |
| --- | --- |
| `id` | Kötelező UUID, a kliens generálja |
| `kind` | `expense`, `income` vagy `transfer` |
| `amount` | Nagyobb, mint 0, legfeljebb 2 tizedes, belefér a `numeric(12,2)` típusba |
| `currency` | Három nagybetű, alapból `HUF` |
| `occurred_on` | Kötelező dátum |
| `purchased_by` | A `HOUSEHOLD_MEMBERS` egyik értéke, alapból az `entered_by` |
| `payer` | `shared` vagy a `HOUSEHOLD_MEMBERS` egyik értéke |
| `tags` | Kiadásnál pontosan egy alap kategória, egyébként üres |
| `entered_by` | Kötelező, a `HOUSEHOLD_MEMBERS` egyik értéke vagy `mock`; a FIN-303 után a belépett felhasználóból jön |
| `note` | Nem kötelező |

## FIN-204 Gold: havi cash-flow és kategória-hónap · 3 SP

**Story:** felhasználóként havonta látni akarom, mennyi jött be, mennyi ment el és mi maradt, hogy tudjam, mire számíthatunk.

**Részfeladatok**

- [x] `gold.monthly_cash_flow` hónap és fizető fél szerint: `income`, `expense`, `net`, `savings_rate` 📅 2026-11-29
- [x] `gold.category_month` hónap, fizető fél és kategória szerint: `expense`, `entry_count` 📅 2026-11-29
- [x] Átvezetés sehol nem számít bevételnek vagy kiadásnak 📅 2026-11-29
- [x] Hónap bejegyzés nélkül is megjelenik nullával, hogy ne torzítsa az átlagot 📅 2026-11-29
- [x] `savings_rate` üres, ha a havi bevétel 0 📅 2026-11-29
- [x] A goldba csak `HUF` kerülhet: más pénznem hibás tesztet ad, mert az összeadás értelmetlen lenne 📅 2026-11-29
- [x] dbt unit tesztek a lenti mintahónapokra; a `dbt build` ezeket is futtatja ([forrás](https://docs.getdbt.com/docs/build/unit-tests)) 📅 2026-11-29

**Elfogadási feltételek**

- [x] Három mintahónapon a gold egyezik a kézi számolással
- [x] Az átvezetés a mintában nem módosítja a bevételt és a kiadást
- [x] A két gold tábla az `mb_reader`-rel olvasható, újraépítés után is
- [x] Az `app_writer` nem éri el a gold sémát

**Mintahónapok a unit teszthez**

A számok kitaláltak, valódi adat nem kerülhet a repóba.

| Hónap | Bevétel | Kiadás | Átvezetés | Egyenleg | Megtakarítási ráta |
| --- | --- | --- | --- | --- | --- |
| 2026-09 | 500 000 Ft | 320 000 Ft | 100 000 Ft | 180 000 Ft | 36% |
| 2026-10 | 500 000 Ft | 450 000 Ft | 0 Ft | 50 000 Ft | 10% |
| 2026-11 | 0 Ft | 120 000 Ft | 0 Ft | −120 000 Ft | üres |

## FIN-205 Metabase Áttekintés dashboard · 2 SP

**Story:** felhasználóként egy képernyőn akarom látni, hogyan áll ez a hónap az előzőhöz és az átlaghoz képest, hogy ne kelljen táblákat olvasnom.

**Részfeladatok**

- [x] A Finance adatforrás szinkronja, hogy a két gold tábla megjelenjen 📅 2026-11-29
- [x] Kártyák: e havi bevétel, kiadás, egyenleg és megtakarítási ráta 📅 2026-11-29
- [x] Összehasonlítás az előző hónappal és az előző 3 lezárt hónap átlagával 📅 2026-11-29
- [x] Kategóriák szerinti bontás az aktuális hónapra 📅 2026-11-29
- [x] Szűrő a fizető félre 📅 2026-11-29
- [x] A dashboard neve `Áttekintés`, a Metabase saját adatbázisában él, így a napi mentés viszi 📅 2026-11-29

**Elfogadási feltételek**

- [x] Ez a hónap, az előző és a 3 lezárt hónap átlaga egy képernyőn látszik
- [x] Egy új bejegyzés a `dbt build` után megjelenik a dashboardon
- [x] A második felhasználó is látja a dashboardot
- [x] A Metabase-ben továbbra sem látszik a bronz és a silver séma

## Események és nyitott kérdések

- [ ] Sprinttervezés, kb. 30 perc 📅 2026-11-16
- [ ] Heti áttekintés, kb. 15 perc 📅 2026-11-23
- [ ] Demó és retró, kb. 30 perc 📅 2026-11-29
- [x] Kiadás: `v0.2.0` a [[Release folyamat]] szerint 📅 2026-11-29

**Eldöntve a tervezés előtt**

- [x] A webapp egyelőre az otthoni stackben fut, közvetlenül a bronzba ír, később a Pi-re költözik; külön repó nem kell ([[0005-monorepo-es-atmeneti-otthoni-webapp|ADR 0005]]).
- [x] Kell külön `purchased_by` mező: a vásárló mindig személy, a fizető fél lehet a közös kártya is.
- [x] Az „átlag” az Áttekintésben az előző 3 lezárt hónap.
- [x] A rendszer egyelőre csak helyben fut, és csak mock adatot kap.
