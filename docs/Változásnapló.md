---
projekt: Pénzügyi nyomkövető
tipus: változásnapló
datum: 2026-10-31
tags: [penzugy, projekt, release]
---

# Változásnapló

Kapcsolódó: [[Release folyamat]] · [[Fejlesztési terv]]

Minden, a szoftvert érintő változás ide kerül, a kiadáskor pedig innen készül a GitHub Release szövege. A vezetés szabályai: [[Release folyamat]].

## Kiadatlan

### Hozzáadva

- FIN-401 Ollama és GLM-OCR a Compose-ban, a `scripts/ollama-pull.sh` letöltővel és a `worker/tools/smoke_receipt.py` próbával.
- FIN-304 Feltöltő képernyő a `/` címen, tartalom alapú típusellenőrzéssel és 20 MB-os határral.
- FIN-305 Helyi postaláda SQLite-tal és a tokennel védett `/inbox` API a workernek.
- FIN-306 Worker: a feltöltés a Garage-ba és a bronzba kerül, hash alapú duplikációszűréssel.
- FIN-408 Kiolvasás a workerben: JSON és szöveges olvasat a `bronze.extraction` táblába, modellazonosítóval; a `scripts/last-extraction.sh` megmutatja a legutóbbit.
- FIN-106 Állapot képernyő a `/status` címen: a stack részei, a feldolgozás lépései, a dbt és a mentés eredménye; a worker healthchecket kapott, a `scripts/status-report.sh`-t a `finance-status.timer` futtatja.

### Frissítési teendők

- A meglévő `home/.env`-be kell egy `WORKER_API_TOKEN`: `echo "WORKER_API_TOKEN=$(openssl rand -hex 24)" >> home/.env`.
- `scripts/ollama-pull.sh`, majd `podman compose -f home/docker-compose.yml up -d --build`.
- `scripts/install-timers.sh`, ez kapcsolja be az állapotjelentést.

## v0.2.0 · 2026-10-31

### Hozzáadva

- FIN-202 dbt projekt, `silver.transactions`, adattesztek és éjszakai `dbt build`.
- FIN-203 Kézi bejegyzés API a bronzba, ismételt küldés elleni védelemmel; a webapp egyelőre az otthoni stackben fut.
- FIN-203 `purchased_by` mező a bronzban, és mock bejegyzések a `scripts/mock-entries.sh` scripttel.
- FIN-204 `gold.monthly_cash_flow` és `gold.category_month`, unit tesztekkel.
- FIN-205 Áttekintés dashboard a `scripts/metabase-dashboard.sh` scripttel.

### Módosítva

- A `scripts/install-backup-timer.sh` helyett `scripts/install-timers.sh`, amely a dbt timerét is telepíti.

### Javítva

- A `scripts/metabase-setup.sh` érthető hibát ír ki, és újrafuttatható.

### Frissítési teendők

- `podman compose -f home/docker-compose.yml up -d --build`, majd `scripts/dbt.sh`, `scripts/metabase-dashboard.sh` és `scripts/install-timers.sh`.

## v0.1.0 · 2026-10-31

### Hozzáadva

- FIN-101 Repó, mappaszerkezet, README, ADR-sablon és az első két ADR.
- FIN-102 Otthoni Compose rögzített verziókkal: Postgres 18.6, Garage 2.5.0, Metabase 0.65.2.4.
- FIN-201 Bronz séma `raw_document`, `extraction` és `manual_entry` táblákkal; a réteg csak hozzáfűzhető.
- FIN-201 Üres silver és gold séma, szerepkörök és jogok.
- FIN-103 A Metabase saját adatai a Postgresben, és a `scripts/metabase-setup.sh` az első beállításhoz.
- FIN-104 Napi mentés resticcel, a `scripts/restore-test.sh` visszaállítási próbával.
- FIN-105 CI: lint, Compose-ellenőrzés, migrációk, bronz teszt és titokkeresés.
- Release folyamat, változásnapló és automatikus GitHub Release.

### Módosítva

- A főgépen rootless Podman futtatja a stacket; a scriptek maguk választanak Podman és Docker között.

### Biztonság

- Adatfájlok tiltása a repóban, commit előtti titokkereséssel, mert a repó nyilvános.
