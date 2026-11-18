---
projekt: Pénzügyi nyomkövető
tipus: változásnapló
datum: 2026-11-17
tags: [penzugy, projekt, release]
---

# Változásnapló

Kapcsolódó: [[Release folyamat]] · [[Fejlesztési terv]]

Minden, a szoftvert érintő változás ide kerül, a kiadáskor pedig innen készül a GitHub Release szövege. A vezetés szabályai: [[Release folyamat]].

## Kiadatlan

### Javítva

- A számlafeldolgozó a mértékegység nélküli, áfakulccsal kezdődő tételsorokat is olvassa; az ingyenes választás nem lesz tétel, és a neve nem ragad a következő tételre.
- A számlán a nap-hónap-év dátum és a szállítási idő is teljesítési dátum.
- Olvasható címke nélkül az áfasorok bruttója a végösszeg; a „Fizetendő összeg” megelőzi egy részösszeg „Fizetendő” sorát.
- Ha a javaslat sorai messze vannak a végösszegtől, a javítás űrlapja egy sorral indul a végösszeggel.
- A `scripts/authelia-user.sh` jelszókérdése látszik, és kiírja, melyik felhasználóé.

### Frissítési teendők

- A worker induláskor a `PARSER_VERSION` 11 miatt minden tárolt szöveget újra feldolgoz, modell nélkül.

## v0.5.0 · 2026-11-17

### Hozzáadva

- A Pi postaláda Compose-fájlja (`pi/`): a webapp Caddy mögött HTTPS-sel a saját domainen, Cloudflare DNS-alapú tanúsítvánnyal, és Authelia kétfaktoros (TOTP) belépéssel, csak a Pi Tailscale-címén.
- `scripts/setup-pi.sh`, `scripts/init-pi-env.sh` és `scripts/authelia-user.sh` a Pi beállításához; `scripts/windows/wsl-autostart.ps1` a WSL ablak nélküli futtatásához és a tükrözött hálózathoz.
- A CI a Pi Compose-fájlját is ellenőrzi.
- `home/docker-compose.tailnet.yml`: a riportok a helyi cím mellett a gép Tailscale-címén is, a `TAILNET_ADDRESS`-szel.
- `scripts/windows/rotate-ssh-key.ps1`: SSH-kulcs cseréje a régi kulcs eltávolításával, próbával az új kulccsal.
- FIN-315 `scripts/pi/pihole-tailnet.sh`: a Pi-hole webszervere a helyi címen, a saját domain nevei helyi rekordként a Pi Tailscale-címén, a Pi nem a Tailscale DNS-ét használja.
- FIN-313 A Pi megerősítése a `scripts/pi/` scriptjeivel: fail2ban, automatikus biztonsági frissítés, korlátozott felhasználó, csak kulcsos SSH és tűzfal önvisszavonó időzítővel.

### Módosítva

- Belépéssel a feltöltő, a szabály és a döntés rögzítője mindig a belépett felhasználó; más nevében a webapp 403-mal elutasít.
- A webapp adatbázis nélkül is fut: a `/health` ilyenkor a postaládát nézi, az `/entries` 503-at ad.
- A worker postaládája az `INBOX_URL`-lel állítható, így a Pi-re mutathat.

### Frissítési teendők

- A Pi beállítása a README „Postaláda a Pi-n” része szerint; az otthoni `home/.env`-ben új, nem kötelező változó az `INBOX_URL`.

### Hozzáadva

- FIN-406 Silver tétel szint: `documents`, `receipt_items`, `document_payments`, `stores`; a kiadásba csak a rendben lévő, jóváhagyott vagy javított dokumentum számít, a kiszerelés a tételnévből jön.
- FIN-206 Riportfelület Streamlitben a `reports/` mappában: Áttekintés és Kiadások, lefúrással az Ellenőrzés képernyőig, közös menüvel a webappal.
- FIN-501 Szabályok oldal a `/rules` címen: tétel- és boltszabályok, amelyek a régi dokumentumokra is érvényesek.
- FIN-409 Betétdíj oldal a `/deposit` címen: a várható DRS-betétdíj, kézi állítás és nullázás; a betétdíj nem kiadás, a beváltott utalvány csökkenti.
- FIN-507 Termékcsaládok és egységár: termék- és kiszerelésszabály a Szabályok oldalon, a tétel `kategória/termékcsalád/termék` besorolást és Ft/kg, Ft/l vagy Ft/db egységárat kap, a `gold.product_prices` havi árnaplót ad.
- A blokkfeldolgozó kiolvassa a tétel fölötti cikkszámot (EAN), és a javítás is megőrzi.
- Árak riport: termékenként a legutóbbi és legolcsóbb egységár, a változás az első hónap óta, havonta boltonként; a Kiadások tételei termékkel és egységárral.
- A blokkfeldolgozó új formái: `D`-nek olvasott áfakód, mértékegység nélküli mérlegelt sor, szóközzel tagolt vagy betű nélküli akciókód, áfakód nélküli táblázatos jegyzék, VISA, MASTERCARD és REPONT a fizetésben, kettőspont nélküli fizetés.
- NVIDIA GPU az Ollamának a `home/docker-compose.gpu.yml` kiegészítéssel, a WSL-es beállítást a `scripts/setup-wsl-gpu.sh` végzi.
- Windowsos fejlesztés WSL2-es Ubuntuban: a `scripts/setup-wsl.sh` telepíti a Docker Engine-t, a Compose-t és a `jq`-t, a README leírja a menetét.

### Módosítva

- A modell betöltve tartása az `OLLAMA_KEEP_ALIVE` változóval állítható; alapból 0 marad, GPU-val 10 perc.
- GPU-val a modell egy CPU-szálat kap, így a kiolvasás alatt a CPU nem pörög.
- GPU-val a kép hosszabb oldala 2000 px (`OLLAMA_MAX_SIDE`), CPU-n marad 1400.
- A vásárlás dátuma a lábléc utolsó dátuma, az akciós szövegek dátuma nem; a boltnév nem lehet a dokumentum címe.
- A visszaváltó automata utalványa nem kiadás, ezért nem kér döntést.
- A modell kontextusa 8192 token (`PROMPT_VERSION` 3); a 4096-os alapértéknél a 2000 px-es fotó olvasása a blokk közepén megszakadt.
- A régebbi beállítással csonkán maradt olvasást a worker induláskor újraolvassa, a blokkot nem kell újra feltölteni.
- A csonka olvasás azonnal újrapróbálódik 16 384, majd 32 768 tokenes kontextussal; a bronz a képtokent, a kontextust és a próbálkozások számát is tárolja.
- Az állapot képernyő Erőforrások csempét kap: szálankénti CPU, RAM, swap, és ha van, NVIDIA GPU. Az Ollama kártya a modell méretét, a GPU-n vagy CPU-n futást, az utolsó olvasást és az utolsó 20 olvasás átlagát mutatja.
- A kiolvasás időadatai (betöltés, kép, szöveg, token/s) a `bronze.extraction` payloadjába is bekerülnek.
- A dbt éjszaka helyett óránként fut, így a döntés egy órán belül a riportokban is látszik.
- A dokumentumok kiadása megjelenik a gold táblákban.
- A számlafeldolgozó felismeri az áfakulccsal kezdődő, mértékegység nélküli táblázatot, a nap-hónap-év dátumot és az áfasorból a végösszeget, ha annak nincs olvasható címkéje. Az ingyenes választások nem lesznek tételek.
- Ha a javaslat sorai messze vannak a végösszegtől, a javítás űrlapja egy sorral indul a végösszeggel.

### Eltávolítva

- A Metabase, a `metabase` adatbázis és a `scripts/metabase-*.sh`; a riportok a Streamlitben vannak.

### Frissítési teendők

- `scripts/backup.sh`, majd `scripts/replace-metabase.sh`: friss jelszót állít be a `report_reader` szerepkörnek, és törli a Metabase adatbázisát. Ez nem visszafordítható, a korábbi `metabase.dump` a mentésben marad.
- `podman compose -f home/docker-compose.yml up -d --build --remove-orphans`, majd `scripts/dbt.sh`. A `migrate` szolgáltatás felveszi a `20261229120000_add_product_rules` migrációt, amely a szabályoknál a `product` és a `pack` típust engedi.
- `scripts/install-timers.sh`: ez állítja át a dbt-t óránkénti futásra.
- A worker induláskor a `PARSER_VERSION` 10 miatt minden tárolt szöveget újra feldolgoz, modell nélkül; a blokkokat nem kell újra feltölteni. A 2000 px csak az új olvasásokra érvényes.
- A `home/.env` `MB_*` és `METABASE_*` sorai ezután törölhetők.
- Új, nem kötelező `.env`-változók: `OLLAMA_KEEP_ALIVE`, `OLLAMA_MAX_SIDE`, `COMPOSE_FILE`. Üresen a korábbi CPU-s viselkedés marad.
- NVIDIA GPU-s gépen, WSL-ben: `scripts/setup-wsl-gpu.sh`, majd a `home/.env`-be `COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml`.

## v0.4.0 · 2026-11-01

### Hozzáadva

- FIN-310 Tömeges feltöltés: egyszerre legfeljebb 20 fájl, közös adatokkal; a dátum opcionális, üresen a blokkról jön.
- FIN-311 Egy dokumentum több fájlból: 2–5 kép vagy PDF egy dokumentumként, a közös sorok egyszer számítanak.
- FIN-402 Saját feldolgozó a szöveges olvasatra: tételek, végösszeg, fizetés, dátum és nyugtaszám a `bronze.receipt_parse` táblában; a tárolt szövegek modell nélkül újra feldolgozhatók.
- FIN-402 `worker/tools/read_folder.py`: repón kívüli mappa kiolvasása a bronz érintése nélkül.
- FIN-404 Automatikus ellenőrzés: összeg, tételszorzat, fizetés, dátum és ismételt blokk; az állapotoldalon az „Ellenőrzésre vár” szám is látszik.
- FIN-412 Számlafeldolgozó: az A4-es számlából szállító, adószám, sorszám, dátumok, tételek, áfaösszesítő és végösszeg lesz; az ismeretlen táblázatú számla `review`, a szállítólevél, a díjbekérő és a proforma nem kiadás.
- FIN-312 PDF-feltöltés: a szöveges PDF modell nélkül, a szkennelt PDF a modellen át dolgozódik fel, a `read_folder` is kezeli; új függőség a `pypdfium2`.
- FIN-413 Újranyitás és előtöltött javítás: minden döntés visszavonható, az elvetett fájl újrafeltöltése újranyitja a dokumentumot, a nem kiadásnál magyarázat látszik, és a szövegből kinyert sorok javaslatként töltik ki a javítást.
- FIN-405 Ellenőrzés képernyő a `/review` címen: az eredeti és a feldolgozott adatok egymás mellett, jóváhagyás, javítás és elvetés; a döntés a `bronze.review_decision` táblába kerül, a dokumentum 30 napig visszanézhető.

### Módosítva

- A modell blokkonként egyszer fut, a JSON-olvasat kikerült, mert rosszul párosította a neveket és az árakat.
- Az állapotoldal „rendben” felirata az ellenőrzések sikerét jelenti, nem az érvényes JSON-t.
- A blokkfeldolgozó felismeri azt a formátumot is, ahol a mennyiség a név fölött áll, és a sor végén áfakód van.
- A feltöltés napja nem számít beírt dátumnak, így a régi dokumentum nem kerül emiatt ellenőrzésre.
- A végösszeg alatti `GÖNGYÖLEG` sorok DRS-utalványként fizetésnek számítanak, több is lehet belőlük, és az Ellenőrzés képernyő módonként mutatja a fizetett összeget.
- A lapok között közös menüsorral lehet váltani.
- Az állapotoldal „Ellenőrzésre vár” száma a nyitott dokumentumokat mutatja, a „Legutóbbi feldolgozások” pedig az újrafeldolgozott eredményt.

### Frissítési teendők

- `podman compose -f home/docker-compose.yml up -d --build`: lefut a migráció, a worker feldolgozza a tárolt szövegeket, és magától visszatölti az elmúlt 30 nap dokumentumait az Ellenőrzés képernyőre.

## v0.3.0 · 2026-11-01

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
