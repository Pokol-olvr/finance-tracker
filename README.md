# Pénzügyi nyomkövető

Kétszemélyes háztartási pénzügyi nyomkövető medallion adatrétegekkel és helyi blokkbeolvasással. A tervek a `docs/` mappában vannak: [Üzleti koncepció](docs/Üzleti%20koncepció.md), [Technikai terv](docs/Technikai%20terv.md), [Fejlesztési terv](docs/Fejlesztési%20terv.md).

A jelenlegi állapot az otthoni alapstack: Postgres a bronz, silver és gold sémákkal, Garage object store és Metabase, napi mentéssel.

## Előfeltételek

- Docker Engine és Docker Compose v2
- `openssl`, `curl`, `jq`
- 3 GB szabad memória a Metabase miatt

## Gyorsindítás

```sh
git clone <repo-url> finance-tracker && cd finance-tracker
scripts/init-env.sh
docker compose -f home/docker-compose.yml up -d
```

A Metabase az első indításkor pár percig készül, utána a `http://127.0.0.1:3000` címen érhető el. Az első beállításhoz töltsd ki a `home/.env` `MB_ADMIN_*` és `MB_SECOND_*` mezőit, majd futtasd a `scripts/metabase-setup.sh`-t. A script létrehozza a két felhasználót, és felveszi a `finance` adatbázist `mb_reader`-ként.

A `scripts/init-env.sh` által generált `MB_ENCRYPTION_SECRET_KEY` és `RESTIC_PASSWORD` értékét mentsd el a jelszókezelőbe. Az első nélkül költözés után a mentett adatbázis-kapcsolatok nem olvashatók, a második nélkül a mentés használhatatlan.

## Felépítés

```text
home/        otthoni Compose, Postgres init, Garage config
pi/          a Pi Compose-fájlja (Sprint 3-tól)
webapp/      FastAPI webapp (Sprint 2-től)
worker/      lehúzás és kinyerés (Sprint 4-től)
dbt/         transzformációk (Sprint 2-től)
migrations/  bronz sémák SQL-migrációi
scripts/     mentés, visszaállítás, segédscriptek
docs/adr/    döntési jegyzetek
```

| Szolgáltatás | Cím | Feladat |
| --- | --- | --- |
| `postgres` | `127.0.0.1:5432` | `finance` és `metabase` adatbázis |
| `migrate` | nincs | Induláskor lefuttatja a `migrations/` mappát, majd kilép |
| `garage` | `127.0.0.1:3900` | S3 API, `raw` bucket |
| `metabase` | `127.0.0.1:3000` | Dashboardok |

Minden adat a `home/data/` alatt van, a helyét a `DATA_DIR` állítja. A Metabase és a Garage címe a `BIND_ADDRESS` változóval a gép Tailscale-címére tehető. A Postgres mindig csak helyben látszik, a Garage admin és RPC portja pedig csak a Compose-hálózaton.

### Szerepkörök a `finance` adatbázisban

| Szerepkör | Jog | Ki használja |
| --- | --- | --- |
| `finance_owner` | A sémák tulajdonosa | Migrációk |
| `app_writer` | Csak beszúrás és olvasás a bronzban | Webapp, worker |
| `dbt_runner` | Olvasás a bronzból, írás a silverbe és a goldba | dbt |
| `mb_reader` | Csak olvasás a goldból | Metabase |

## Migrációk

A migrációk sima SQL-fájlok a `migrations/` mappában, a [dbmate](https://github.com/amacneil/dbmate) futtatja őket. Az új fájl nevének eleje időbélyeg, és az alkalmazásukhoz elég újra lefuttatni a `migrate` szolgáltatást:

```sh
docker compose -f home/docker-compose.yml run --rm migrate
scripts/test-bronze.sh
```

A bronz csak hozzáfűzhető: az UPDATE, a DELETE és a TRUNCATE a tulajdonosnál is hibát ad. A javítás a silverben történik.

## Mentés

A `scripts/backup.sh` a futó stacken dolgozik:

1. `pg_dump` a `finance` és a `metabase` adatbázisról a `home/backup/dumps/` mappába, a `finance` táblák sorszámával együtt.
2. A Garage `raw` bucket tükrözése a `home/backup/garage-raw/` mappába.
3. restic pillanatkép a `RESTIC_REPO_DIR` tárolóba, 7 napi, 4 heti és 6 havi megőrzéssel.

A `RESTIC_REPO_DIR` éles használatra külső meghajtóra mutasson; alapból ugyanazon a lemezen van, és a script erre figyelmeztet.

### Ütemezés

A systemd timer naponta 03:30-kor futtatja a mentést, és ha a gép ki volt kapcsolva, induláskor pótolja. A `scripts/systemd/finance-backup.service` fájlban írd át a repó helyét, majd:

```sh
cp scripts/systemd/finance-backup.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now finance-backup.timer
loginctl enable-linger "$USER"
```

### Visszaállítás

A `scripts/restore-test.sh` ellenőrzi a restic tárolót, a legutóbbi pillanatképet egy eldobható Postgresbe tölti, és a sorszámokat a mentéskor rögzítettel veti össze. Az élő adathoz nem nyúl.

Egy elveszett fájl visszahozása a Garage-ba, a `home/` mappából futtatva:

```sh
docker compose run --rm restic snapshots
docker compose run --rm restic restore latest --target /backup/restore --include /backup/garage-raw/fajl.jpg
docker compose run --rm rclone copyto /backup/restore/backup/garage-raw/fajl.jpg garage:raw/fajl.jpg
```

## Fejlesztés

A repó nyilvános, ezért csak a szoftver váza kerül bele. Valódi blokk, bérpapír, kivonat, dump, modell és titok soha; a tesztekhez csak kitalált adat használható.

Klónozás után kapcsold be a commit előtti ellenőrzést. Ez a tiltott fájltípusokat és a titkokat keresi, és Docker vagy Podman kell hozzá:

```sh
git config core.hooksPath .githooks
```

- A `main` ágra csak pull requestből kerül kód, a másik fél jóváhagyásával és zöld pipeline-nal.
- A CI (`.github/workflows/ci.yml`) minden pushra futtatja a lintet (ruff, sqlfluff), az adatfájlok tiltását, a titokkeresést (gitleaks), a Compose-ellenőrzést, a migrációkat és a bronz tesztet.
- A döntési jegyzetek a [docs/adr/](docs/adr/) mappában vannak.
- Podman esetén a scriptek a `COMPOSE` változóval kapják meg a Compose-parancsot.
