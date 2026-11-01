# Pénzügyi nyomkövető

Kétszemélyes háztartási pénzügyi nyomkövető medallion adatrétegekkel és helyi blokkbeolvasással. A tervek a `docs/` mappában vannak: [Üzleti koncepció](docs/Üzleti%20koncepció.md), [Technikai terv](docs/Technikai%20terv.md), [Fejlesztési terv](docs/Fejlesztési%20terv.md).

A jelenlegi állapot az otthoni stack: Postgres a bronz, silver és gold sémákkal, Garage object store, kézi bejegyzés API és blokkfeltöltés, a GLM-OCR kiolvasásával, dbt és Metabase Áttekintés dashboard, napi mentéssel, és egy állapot képernyő a stack minden részéről. Egyelőre minden helyben fut, mock adattal és néhány saját próbablokkal.

## Előfeltételek

- Rootless Podman, a `scripts/setup-podman.sh` egyszeri beállításával (Fedora); a CI Dockert használ, az is működik
- `openssl`, `curl`, `jq`
- 3 GB szabad memória a Metabase miatt, és további 5 GB a kiolvasás idejére
- 3 GB szabad lemez a modellnek

## Gyorsindítás

```sh
git clone <repo-url> finance-tracker && cd finance-tracker
scripts/setup-podman.sh
scripts/init-env.sh
scripts/ollama-pull.sh
podman compose -f home/docker-compose.yml up -d --build
```

A Metabase az első indításkor pár percig készül, utána a `http://127.0.0.1:3000` címen érhető el. Az első beállításhoz töltsd ki a `home/.env` `MB_ADMIN_*` és `MB_SECOND_*` mezőit, majd futtasd a `scripts/metabase-setup.sh`-t. A script létrehozza a két felhasználót, és felveszi a `finance` adatbázist `mb_reader`-ként. A `scripts/metabase-dashboard.sh` ezután elkészíti az Áttekintés dashboardot. Mindkettő újrafuttatható.

A `scripts/init-env.sh` által generált `MB_ENCRYPTION_SECRET_KEY` és `RESTIC_PASSWORD` értékét mentsd el a jelszókezelőbe. Az első nélkül költözés után a mentett adatbázis-kapcsolatok nem olvashatók, a második nélkül a mentés használhatatlan.

## Felépítés

```text
home/        otthoni Compose, Postgres init, Garage config
pi/          a Pi Compose-fájlja (Sprint 6-tól)
webapp/      FastAPI webapp (Sprint 2-től)
worker/      lehúzás és kiolvasás (Sprint 3-tól)
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
| `inbox-init` | nincs | Induláskor beállítja a postaláda mappájának tulajdonosát, majd kilép |
| `webapp` | `127.0.0.1:8000` | Feltöltő és állapot képernyő, kézi bejegyzés API és postaláda; belépés nélkül, ezért csak helyben látszik |
| `ollama` | nincs | A GLM-OCR modell futtatója, csak a Compose-hálózaton |
| `worker` | nincs | A postaládából a Garage-ba és a bronzba viszi a feltöltéseket, és kiolvastatja őket |
| `metabase` | `127.0.0.1:3000` | Dashboardok |

Minden adat a `home/data/` alatt van, a helyét a `DATA_DIR` állítja. A Metabase és a Garage címe a `BIND_ADDRESS` változóval a gép Tailscale-címére tehető. A Postgres mindig csak helyben látszik, a Garage admin és RPC portja pedig csak a Compose-hálózaton.

A konténerek rootless Podmanben a felhasználóhoz tartoznak, ezért a `home/data/postgres` törléséhez `podman unshare rm -rf home/data` kell. A `home/data/inbox` és a `home/data/ollama` nem kerül a mentésbe: az első átmeneti tároló, a második újra letölthető.

### Szerepkörök a `finance` adatbázisban

| Szerepkör | Jog | Ki használja |
| --- | --- | --- |
| `finance_owner` | A sémák tulajdonosa | Migrációk |
| `app_writer` | Csak beszúrás és olvasás a bronzban | Webapp, worker |
| `dbt_runner` | Olvasás a bronzból, írás a silverbe és a goldba | dbt |
| `mb_reader` | Csak olvasás a goldból | Metabase |

## Kézi bejegyzés és adatút

A bejegyzés az API-n át kerül a bronzba, a `dbt build` pedig ebből építi a silvert és a goldot. A bronzba került sor nem törölhető és nem javítható, ezért az azonosítót a kliens adja: ugyanaz az `id` másodszor már nem ír.

```sh
curl -H 'Content-Type: application/json' http://127.0.0.1:8000/entries -d '{
  "id": "2f5b9c1e-7a54-4f0e-9d3a-0c1b2a3d4e5f",
  "kind": "expense",
  "amount": "18450.10",
  "occurred_on": "2026-11-16",
  "entered_by": "mock",
  "purchased_by": "person_a",
  "payer": "shared",
  "tags": ["élelmiszer"]
}'
scripts/dbt.sh
```

A `purchased_by` és a `payer` a `HOUSEHOLD_MEMBERS` kódjait használja, a `payer` lehet `shared` is. A `scripts/mock-entries.sh` hat hónapnyi kitalált adatot tölt be, és újrafuttatható. A webapp tesztjei a `scripts/test-webapp.sh` paranccsal futnak, és a bronzban nem hagynak adatot.

## Blokk feltöltése és kiolvasása

A `http://127.0.0.1:8000` oldalon kell megadni a fotókat, a feltöltőt, a vásárlót, a fizető felet és legalább egy címkét. A képet JPEG, PNG, HEIC vagy WebP formátumban, fájlonként legfeljebb 20 MB-ig fogadja. A telefon a FIN-308-ig nem éri el az oldalt, ezért a fotót előbb a laptopra kell áttenni.

- **Több blokk egyszerre:** legfeljebb 20 fájl tölthető fel körönként, behúzással is. A megadott adatok mindegyikre érvényesek, és egy rossz fájl nem állítja meg a többit. Több fájlnál a dátum üres marad, és a blokkról olvassuk ki.
- **Hosszú blokk több képből:** az „Egy hosszú blokk több képből” kapcsolóval 2–5 kép tartozik egy blokkhoz, a nyilakkal rendezhető sorrendben. A két képen is látszó sorok egyszer számítanak. Ha bármelyik fájl hibás, egyik sem kerül be.

A worker percenként megnézi a postaládát, és tételenként végigviszi a folyamatot:

1. Letölti a fájlt, és ellenőrzi a hash-t.
2. Ha ez a kép még nincs a bronzban, a `raw` bucketbe teszi `photo/ÉÉÉÉ/HH/<sha256>.<kiterjesztés>` kulccsal, és beírja a `bronze.raw_document` táblába.
3. Szöveggé olvastatja a modellel, és az eredményt a `bronze.extraction` táblába teszi.
4. A szövegből a saját feldolgozó tételeket, végösszeget és fizetési adatokat készít, ellenőrzi őket, és az eredményt a `bronze.receipt_parse` táblába teszi.
5. Lezárja a tételt, a fájl ekkor törlődik a postaládából.

Ha az Ollama vagy a Garage nem érhető el, a tétel nyitva marad, és a worker a következő körben folytatja. A rossz kimenet is a bronzba kerül, és lezárja a tételt. A tételek sorban futnak. Az indoklás: [ADR 0009](docs/adr/0009-szabalyalapu-blokkfeldolgozo.md).

| Ellenőrzés | Szabály |
| --- | --- |
| `sum` | A tételek, a betétdíj, a kedvezmény és az utalvány összege a végösszeg |
| `line_total` | Mennyiség × egységár = érték, 1 Ft tűréssel |
| `payment` | Fizetett − visszajáró = végösszeg, készpénznél 2 Ft tűréssel |
| `date` | A beírt és a beolvasott dátum egyezik |
| `duplicate` | Az adószám és a nyugtaszám másik blokkon nem szerepel |

A blokk állapota `ok`, ha egyik ellenőrzés sem bukott el, `review`, ha valamelyik igen, és `unparsed`, ha nincs tétel vagy végösszeg. Egy ellenőrzés kimarad, ha hiányzik hozzá az adat. A `worker/app/receipt_parser.py` szabályai magyar blokkformátumokra készültek. Új formátumhoz szabályt és kitalált tesztblokkot kell felvenni a `worker/tests/receipts/` mappába, majd növelni a `PARSER_VERSION` értékét. A worker induláskor a tárolt szövegeket modell nélkül újra feldolgozza.

A legutóbbi kiolvasás, illetve az utolsó három:

```sh
scripts/last-extraction.sh
scripts/last-extraction.sh 3
```

A kimenetben a szöveges olvasat, a feldolgozott tételek és az ellenőrzések is látszanak. Saját blokk adatát is tartalmazhatja, ezért nem kerülhet a repóba vagy hibajegybe. A bronzba került blokk nem törölhető, csak a FIN-309 építi újra üresen az adatbázist és a Garage-ot. A fotót a napi mentés a restic-pillanatképekbe is beviszi.

A modell kitalált mintablokkon így próbálható ki, ez a bronzba nem ír:

```sh
podman compose -f home/docker-compose.yml run --rm --no-deps worker python -m tools.smoke_receipt
```

Egy repón kívüli mappa képei a bronz érintése nélkül is kiolvashatók. Képenként egy `.txt` és egy `.json` fájl készül, megszakítás után a futás folytatható:

```sh
podman compose -f home/docker-compose.yml run --rm --no-deps --user 0 \
  -v "$HOME/blokk-mintak:/be:ro,z" -v "$HOME/blokk-eredmeny:/ki:z" \
  worker python -m tools.read_folder /be /ki
```

A kimenet nem kerülhet a repóba: a szöveges fájlokat a commit előtti ellenőrzés nem szűri.

A worker tesztjei a `scripts/test-worker.sh` paranccsal futnak, valódi Garage-dzsal és Postgresszel, a modellt egy csonk helyettesíti.

## Állapot képernyő

A `http://127.0.0.1:8000/status` oldal kilenc kártyán mutatja a stack részeit: Feltöltés, Worker, Ollama, Garage, Postgres, Metabase, dbt, Mentés és Gép. Fölöttük látszik az összkép és az aktuális feldolgozási lépés az eltelt idővel, alattuk a legutóbbi feldolgozások. Az oldal 5 másodpercenként frissül, az adatai a `/status.json` címen is elérhetők.

| Felirat | Jelentés |
| --- | --- |
| Hiba | Egy szolgáltatás nem fut vagy nem egészséges, a modell nincs letöltve, vagy az utolsó dbt-futás vagy mentés hibás |
| Nincs friss adat | Egy jelentés 60 másodpercnél régebbi, ezért a kártya szürke, nem zöld |
| Feldolgozás fut | A worker tételen dolgozik |
| Várakozik | Van nyitott tétel, a worker a következő körre vár |
| Minden rendben | Egyik sem igaz |

Az adatot két forrás küldi a webappnak, a `WORKER_API_TOKEN` tokennel. A `scripts/status-report.sh`-t a `finance-status.timer` 15 másodpercenként futtatja, ez jelenti a szolgáltatásokat, a timereket, a Garage és a Postgres adatait, a lemezt és a memóriát. A worker a lépéseit és az Ollama állapotát jelenti, külön szálon, mert a modell hívása percekig tart. A modell a betöltése alatt még `Betöltve: nem` állapotot mutat.

A „rendben” csak olyan blokkra jelenik meg, amelynek az ellenőrzései nem buktak el, az „Ellenőrzésre vár” szám a többit mutatja. Az oldalon nincs fájlnév és blokktartalom, előzményt és riasztást nem tárol. Ha a webapp nem fut, az oldal sem nyílik meg, ekkor a `podman compose -f home/docker-compose.yml ps` marad. Az indoklás: [ADR 0008](docs/adr/0008-allapot-kepernyo-a-webappban.md).

## Migrációk

A migrációk sima SQL-fájlok a `migrations/` mappában, a [dbmate](https://github.com/amacneil/dbmate) futtatja őket. Az új fájl nevének eleje időbélyeg, és az alkalmazásukhoz elég újra lefuttatni a `migrate` szolgáltatást:

```sh
podman compose -f home/docker-compose.yml run --rm migrate
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

A systemd timerek naponta 03:00-kor a `dbt build`-et, 03:30-kor a mentést futtatják, és ha a gép ki volt kapcsolva, induláskor pótolják. A harmadik timer 15 másodpercenként az állapotjelentést küldi. A telepítés:

```sh
scripts/install-timers.sh
```

### Visszaállítás

A `scripts/restore-test.sh` ellenőrzi a restic tárolót, a legutóbbi pillanatképet egy eldobható Postgresbe tölti, és a sorszámokat a mentéskor rögzítettel veti össze. Az élő adathoz nem nyúl.

Egy elveszett fájl visszahozása a Garage-ba, a `home/` mappából futtatva:

```sh
podman compose run --rm restic snapshots
podman compose run --rm restic restore latest --target /backup/restore --include /backup/garage-raw/fajl.jpg
podman compose run --rm rclone copyto /backup/restore/backup/garage-raw/fajl.jpg garage:raw/fajl.jpg
```

## Fejlesztés

A repó nyilvános, ezért csak a szoftver váza kerül bele. Valódi blokk, bérpapír, kivonat, dump, modell és titok soha; a tesztekhez csak kitalált adat használható.

Klónozás után kapcsold be a commit előtti ellenőrzést. Ez a tiltott fájltípusokat és a titkokat keresi, és Docker vagy Podman kell hozzá:

```sh
git config core.hooksPath .githooks
```

- A `main` ágra csak pull requestből kerül kód, zöld pipeline-nal. Egy fejlesztő van, ezért kötelező jóváhagyás nincs.
- A CI (`.github/workflows/ci.yml`) minden pushra futtatja a lintet (ruff, sqlfluff), az adatfájlok tiltását, a titokkeresést (gitleaks), a Compose-ellenőrzést, a migrációkat, a bronz tesztet, a dbt-t, valamint a webapp és a worker tesztjeit.
- A döntési jegyzetek a [docs/adr/](docs/adr/) mappában vannak.
- A változások a [Változásnapló](docs/Változásnapló.md) Kiadatlan részébe kerülnek, a kiadás menete a [Release folyamat](docs/Release%20folyamat.md) dokumentumban van.
- A scriptek a `docker compose` és a `podman compose` közül maguk választanak, a `COMPOSE` változó ezt felülírja.
