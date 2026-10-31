---
projekt: Pénzügyi nyomkövető
sprint: S1
kezdes: 2026-11-02
vege: 2026-11-15
story_pont: 15
tags: [penzugy, sprint]
---

# Sprint 1

Vissza: [[Fejlesztési terv]]

## Sprint cél

**Az otthoni alapstack fut, az adat túléli az újraindítást, naponta mentődik, és a bronz réteg csak hozzáfűzhető.** A sprint 2026-11-02 és 2026-11-15 között tart, 15 story ponttal.

| Kulcs | Jegy | SP | Függ tőle |
| --- | --- | --- | --- |
| FIN-101 | Git repo és mappaszerkezet | 2 | — |
| FIN-102 | Otthoni Compose: Postgres, Garage, Metabase | 3 | FIN-101 |
| FIN-201 | Bronz sémák, csak hozzáfűzés | 3 | FIN-102 |
| FIN-103 | A Metabase beállításai a Postgresben | 1 | FIN-102 |
| FIN-104 | Napi mentés és visszaállítási próba | 3 | FIN-102, FIN-201 |
| FIN-105 | CI: lint, migrációk, Compose-ellenőrzés | 3 | FIN-101, FIN-201 |

Javasolt sorrend: először a FIN-101 és a FIN-102. Utána párhuzamosan mehet a FIN-201 és a FIN-103, végül a FIN-104 és a FIN-105, mert ezek a bronz sémára épülnek.

## FIN-101 Git repo és mappaszerkezet · 2 SP

**Story:** fejlesztőként egy közös repót szeretnék, egyértelmű mappákkal, hogy mindketten ugyanabból dolgozzunk, és minden új gépen percek alatt induljon a stack.

**Részfeladatok**

- [x] Repo létrehozása: nyilvános GitHub-repó 📅 2026-11-15
- [x] Mappaszerkezet a lenti minta szerint, üres helyeken `.gitkeep` 📅 2026-11-15
- [x] `.gitignore`: `data/`, `backup/`, `.env`, Python- és dbt-melléktermékek 📅 2026-11-15
- [x] `home/.env.example` minden szükséges változóval, értékek nélkül 📅 2026-11-15
- [x] README: mi ez, előfeltételek, gyorsindítás három parancsban 📅 2026-11-15
- [x] `docs/adr/0001-adr-sablon.md` és az első két ADR: Garage a MinIO helyett, Tailscale a WireGuard helyett 📅 2026-11-15
- [ ] Ág-szabály: `main` csak pull requestből, a másik fél jóváhagyásával 📅 2026-11-15

**Elfogadási feltételek**

- [x] Egy tiszta gépen a klónozás, a `.env` kitöltése és a `docker compose up` után a stack elindul
- [x] A `git status` a stack futtatása után is tiszta (az adat nem kerül a repóba)
- [ ] A `main` ágra közvetlen push nem megy át

**Mappaszerkezet**

```text
finance-tracker/
  home/        otthoni Compose, Postgres init, Garage config
  pi/          a Pi Compose-fájlja (Sprint 3-tól)
  webapp/      FastAPI webapp (Sprint 2-től)
  worker/      lehúzás és kinyerés (Sprint 4-től)
  dbt/         transzformációk (Sprint 2-től)
  migrations/  bronz sémák SQL-migrációi
  scripts/     mentés, visszaállítás, segédscriptek
  docs/adr/    döntési jegyzetek
```

## FIN-102 Otthoni Compose: Postgres, Garage, Metabase · 3 SP

**Story:** fejlesztőként egy paranccsal akarom elindítani az otthoni alapszolgáltatásokat úgy, hogy minden adat egy mappában legyen, és újraindítás után megmaradjon.

**Részfeladatok**

- [x] `home/docker-compose.yml` három szolgáltatással: `postgres`, `garage`, `metabase` 📅 2026-11-15
- [x] Rögzített képverziók (pl. `postgres:18`, a Garage és a Metabase konkrét verziócímkéje), nem `latest` 📅 2026-11-15
- [x] Bind mountok a `data/` alá: `data/postgres`, `data/garage/meta`, `data/garage/data` 📅 2026-11-15
- [x] Postgres init script: két adatbázis (`finance`, `metabase`) és a szerepkörök (lásd lent) 📅 2026-11-15
- [x] Garage egycsomópontos beállítás: layout, egy `raw` bucket és egy kulcs a workernek 📅 2026-11-15
- [x] Healthcheck a Postgresre; a Metabase csak az egészséges Postgres után induljon 📅 2026-11-15
- [x] `restart: unless-stopped` mindenhol 📅 2026-11-15
- [x] Portok csak helyben vagy a Tailscale-címen: a Postgres és a Garage admin portja ne látsszon a hálózaton 📅 2026-11-15

**Elfogadási feltételek**

- [x] `docker compose up -d` után mindhárom szolgáltatás egészséges
- [x] Egy teszttábla és egy feltöltött tesztfájl a `docker compose down` és `up` után is megvan
- [x] A Metabase felülete elérhető a böngészőből

**Szerepkörök a `finance` adatbázisban**

| Szerepkör | Jog | Ki használja |
| --- | --- | --- |
| `finance_owner` | A sémák tulajdonosa | Migrációk |
| `app_writer` | Csak beszúrás a bronzba | Webapp, worker |
| `dbt_runner` | Olvasás a bronzból, írás a silverbe és a goldba | dbt |
| `mb_reader` | Csak olvasás a goldból | Metabase |

## FIN-201 Bronz sémák, csak hozzáfűzés · 3 SP

**Story:** adatgazdaként azt akarom, hogy a bronzba bekerült adat soha ne változhasson, hogy minden későbbi feldolgozás visszavezethető legyen az eredetire.

**Részfeladatok**

- [x] Migrációs eszköz bevezetése: sima SQL-migrációk, pl. dbmate (MIT), a `migrations/` mappában 📅 2026-11-15
- [x] `bronze` séma és három tábla: `raw_document`, `extraction`, `manual_entry` 📅 2026-11-15
- [x] Pénzösszeg mindig `numeric(12,2)` és pénznemkód, időpont mindig `timestamptz` 📅 2026-11-15
- [x] Trigger, amely minden UPDATE-et, DELETE-et és TRUNCATE-et hibával elutasít, a tulajdonosnál is 📅 2026-11-15
- [x] Jogok: `app_writer` csak INSERT és SELECT; senkinek nincs UPDATE, DELETE, TRUNCATE 📅 2026-11-15
- [x] Üres `silver` és `gold` séma a `dbt_runner` és az `mb_reader` jogaival 📅 2026-11-15

**Elfogadási feltételek**

- [x] A migrációk üres adatbázison hibátlanul lefutnak, és újrafuttatva sem okoznak hibát
- [x] Beszúrás `app_writer`-ként működik
- [x] UPDATE és DELETE bármelyik szerepkörrel hibát ad
- [x] Ugyanaz a fájl-hash másodszorra nem szúrható be

**Táblák**

| Tábla | Fő mezők |
| --- | --- |
| `raw_document` | id, sha256 (egyedi), object_key, source_type, uploaded_by, uploaded_at, purchase_date, payer, tags, ingested_at |
| `extraction` | id, document_id, model_name, model_version, prompt_version, payload (jsonb), created_at |
| `manual_entry` | id, entered_by, entered_at, kind (expense, income, transfer), amount, currency, occurred_on, payer, tags, note |

**Minta: egy tábla és a hozzáfűzés-védelem**

```sql
create schema if not exists bronze;

create table bronze.raw_document (
  id            uuid primary key default gen_random_uuid(),
  sha256        text not null unique,
  object_key    text not null,
  source_type   text not null check (source_type in ('photo','pdf','email','payslip','statement')),
  uploaded_by   text not null,
  uploaded_at   timestamptz not null,
  purchase_date date,
  payer         text,
  tags          text[] not null default '{}',
  ingested_at   timestamptz not null default now()
);

create function bronze.forbid_change() returns trigger
language plpgsql as $$
begin
  raise exception 'A bronz réteg csak hozzáfűzhető (%)', tg_table_name;
end $$;

create trigger raw_document_append_only
  before update or delete or truncate on bronze.raw_document
  for each statement execute function bronze.forbid_change();
```

## FIN-103 A Metabase beállításai a Postgresben · 1 SP

**Story:** felhasználóként azt akarom, hogy a dashboardjaim megmaradjanak, ha a Metabase-konténert újra kell húzni vagy a stack költözik.

**Részfeladatok**

- [x] A Metabase a saját adatait a `metabase` adatbázisban tárolja, a `MB_DB_TYPE`, `MB_DB_HOST`, `MB_DB_PORT`, `MB_DB_DBNAME`, `MB_DB_USER`, `MB_DB_PASS` változókkal 📅 2026-11-15
- [ ] `MB_ENCRYPTION_SECRET_KEY` beállítása, és a kulcs elmentése a jelszókezelőbe: enélkül költözés után a mentett adatbázis-kapcsolatok nem olvashatók 📅 2026-11-15
- [ ] Két felhasználó létrehozása a Metabase-ben 📅 2026-11-15
- [ ] Adatforrásként a `finance` adatbázis felvétele `mb_reader`-ként, így a Metabase csak a goldot látja 📅 2026-11-15

**Elfogadási feltételek**

- [x] Egy próbadashboard a `docker compose rm -sf metabase` és az újraindítás után is megvan
- [x] A Metabase-ben a bronz és a silver séma nem látszik

## FIN-104 Napi mentés és visszaállítási próba · 3 SP

**Story:** felhasználóként biztos akarok lenni benne, hogy egy lemezhiba vagy rossz parancs után sem vész el a pénzügyi adatunk.

**Részfeladatok**

- [x] `scripts/backup.sh`: `pg_dump -Fc` a `finance` és a `metabase` adatbázisról a `backup/` mappába 📅 2026-11-15
- [x] A Garage `raw` bucket tükrözése rclone-nal egy helyi mappába 📅 2026-11-15
- [x] restic tároló a külső meghajtón; a mentés a dumpot és a tükröt viszi 📅 2026-11-15
- [x] Megőrzés: `restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune` 📅 2026-11-15
- [ ] Ütemezés a gazdagépen (systemd timer vagy cron), naponta egyszer 📅 2026-11-15
- [ ] A restic jelszó a jelszókezelőben is legyen: nélküle a mentés használhatatlan 📅 2026-11-15
- [x] `scripts/restore-test.sh`: ideiglenes Postgres-konténerbe visszatölti a legutóbbi mentést, és összeveti a sorok számát 📅 2026-11-15

**Elfogadási feltételek**

- [ ] Egy éjszakai futás után a restic tárolóban megjelenik a pillanatkép
- [x] A visszaállítási próba egyező sorszámokkal zárul
- [x] Egy törölt tesztfájl a tükörből visszahozható
- [x] A folyamat le van írva a README-ben

## FIN-105 CI: lint, migrációk, Compose-ellenőrzés · 3 SP

**Story:** fejlesztőként azt akarom, hogy minden push automatikusan ellenőrizve legyen, és hibás migráció vagy kiszivárgott jelszó ne kerülhessen a `main` ágra.

**Részfeladatok**

- [x] Pipeline GitHub Actionsben 📅 2026-11-15
- [x] Lint: ruff a Python-kódra, SQL-lint a migrációkra 📅 2026-11-15
- [x] `docker compose config` ellenőrzés a `home/` mappára 📅 2026-11-15
- [x] Migrációk futtatása egy Postgres-szolgáltatáskonténeren, utána egy rövid teszt: beszúrás működik, UPDATE hibát ad 📅 2026-11-15
- [x] Titokkeresés (pl. gitleaks), hogy jelszó vagy kulcs ne kerüljön a repóba 📅 2026-11-15
- [x] Üres helyőrző lépés a `dbt build`-nek, amely a FIN-202-vel kapcsol be a 2. sprintben 📅 2026-11-15
- [ ] A pull request csak zöld pipeline-nal olvasztható be 📅 2026-11-15

**Elfogadási feltételek**

- [ ] Egy szándékosan hibás migráció piros pipeline-t ad
- [ ] Egy `.env`-ből bemásolt jelszó piros pipeline-t ad
- [ ] Tiszta ágon a pipeline zöld, és pár percen belül lefut

## Események és nyitott kérdések

- [ ] Sprinttervezés, kb. 30 perc 📅 2026-11-02
- [ ] Heti egyeztetés, kb. 15 perc 📅 2026-11-09
- [ ] Demó és retró, kb. 30 perc 📅 2026-11-15

**A tervezésen eldöntendő**

- [x] Hol legyen a repo: nyilvános GitHub-repó, amelybe valódi adat nem kerül. 📅 2026-11-02
- [ ] Mi a mentés célja: külső USB-lemez, vagy a Proxmox egy másik lemeze? Egy példány érdemes házon kívül is. 📅 2026-11-02
- [ ] Ki melyik jegyet viszi? Javaslat: az egyikőtök a FIN-102 → FIN-103 → FIN-104 vonalat, a másik a FIN-201 → FIN-105 vonalat. 📅 2026-11-02
