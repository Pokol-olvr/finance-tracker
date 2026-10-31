---
projekt: Pénzügyi nyomkövető
sprint: S3
kezdes: 2026-11-30
vege: 2026-12-13
story_pont: 15
tags: [penzugy, sprint]
---

# Sprint 3

Vissza: [[Fejlesztési terv]]

## Sprint cél

**Egy böngészőből feltöltött, kitalált blokkfotó a helyi postaládán át a Garage-ba és a bronzba kerül, és a laptopon futó GLM-OCR JSON-t ad egy mintablokkból.** A sprint 2026-11-30 és 2026-12-13 között tart, 15 story ponttal.

| Kulcs | Jegy | SP | Függ tőle |
| --- | --- | --- | --- |
| FIN-401 | Ollama és GLM-OCR a laptop CPU-ján | 2 | — |
| FIN-304 | Feltöltő képernyő | 5 | FIN-203 |
| FIN-305 | Postaláda API a workernek | 3 | FIN-304 |
| FIN-306 | Worker: Garage, duplikációszűrés, bronz rekord | 5 | FIN-102, FIN-201, FIN-305 |

Javasolt sorrend: először a FIN-401, utána a FIN-304, a FIN-305 és a FIN-306. A modell és a worker a sprintben még nincs összekötve: a kinyerés a FIN-402-vel, a 4. sprintben kerül a folyamatba.

**Helyi postaláda:** a Pi a 6. sprintben jön, de a postaláda API már most elkészül, helyben futtatva. A worker így a költözéskor csak egy másik címre mutat ([[0006-blokkbeolvasas-a-pi-elott|ADR 0006]]). A telefon addig nem éri el a webappot, a feltöltés böngészőből történik.

**Mock adat:** a tesztek blokkjai kódból készülnek, képfájl nem kerül a repóba. A bronz és a Garage tartalma az első éles használat előtt üresen újraépül (FIN-309).

## FIN-401 Ollama és GLM-OCR a laptop CPU-ján · 2 SP

**Story:** fejlesztőként a laptopon akarom futtatni a képfelismerő modellt, hogy a blokkbeolvasás a főgép és a Pi nélkül is fejleszthető legyen.

**Részfeladatok**

- [ ] `ollama` szolgáltatás a Compose-ban: `docker.io/ollama/ollama:0.40.13`, `restart: unless-stopped`, port nélkül 📅 2026-12-13
- [ ] Modellek a `data/ollama` mappában, így újraindítás után nem töltődnek le újra 📅 2026-12-13
- [ ] `scripts/ollama-pull.sh`: a `glm-ocr` letöltése, a modell azonosítójának kiírása 📅 2026-12-13
- [ ] `OLLAMA_MODEL` és `OLLAMA_NUM_THREAD` a `.env.example`-ben, alapból `glm-ocr` és 10 📅 2026-12-13
- [ ] `worker/tools/smoke_receipt.py`: kódból rajzolt, kitalált blokkot küld a modellnek, és ellenőrzi a kimenetet 📅 2026-12-13
- [ ] README: a modell letöltése és a futási idő a laptopon 📅 2026-12-13

**Elfogadási feltételek**

- [ ] Egy kitalált mintablokkra érvényes JSON jön vissza, 1 percen belül
- [ ] A kimenet a `store`, `date`, `items` és `total` mezőket tartalmazza
- [ ] A konténer újraindítása után a modell nem töltődik le újra
- [ ] Az Ollama portja nem látszik a gazdagépen
- [ ] A modell futása közben a stack szolgáltatásai egészségesek maradnak

**Mérés a laptopon**

2026-10-31-én, Ollama 0.40.13-mal, CPU-n, 10 szálon mérve. A minták számítógéppel rajzolt, kitalált blokkok, ezért a valódi, gyűrött fotókra nem bizonyítanak semmit; az időkre viszont lehet tervezni.

| Modell | Letöltés | Teljes idő | Kép feldolgozása | Válasz írása | Memória | Ezres tagolás |
| --- | --- | --- | --- | --- | --- | --- |
| `glm-ocr` | 2,7 GB | 17 mp | 10 mp | 5 mp | kb. 5 GB | helyes |
| `qwen3-vl:4b` | 3,3 GB | 56 mp | 41 mp | 12 mp | kb. 8 GB | hibás |
| `qwen3-vl:8b` | 6,2 GB | 92 mp | 69 mp | 19 mp | nincs külön mérve | hibás |

**A modell hívása**

| Beállítás | Érték | Miért |
| --- | --- | --- |
| Prompt | A kért JSON szerkezete, mintául | A GLM-OCR séma alapján nyer ki adatot |
| `num_thread` | 10 | Az Ollama alapból kb. 2 magot használt |
| `num_predict` | 500 | A kimenet hossza legyen korlátos |
| `temperature` | 0 | A kinyerés legyen ismételhető |
| `keep_alive` | `0` | A modell a futás után felszabadítja a memóriát |

**Tanulságok a FIN-402-höz**

- **Ékezetek:** az `Ő` többször `Ö` lett (`ŐSZIBARACK` helyett `ÖSZIBARACK`), a többi ékezetes betű helyes volt.
- **Fizetési mód:** JSON módban üres maradt, szöveges módban (`Text Recognition:`) a `SZÉP-KÁRTYA` sor is helyesen megjött.
- **Dátum:** a blokkon lévő formában jön vissza, ezért `ÉÉÉÉ-HH-NN` alakra kell hozni.
- **Kimenet:** ```` ```json ```` jelölésben érkezik, ezt feldolgozás előtt le kell vágni.
- **Kép:** a HEIC-et át kell alakítani, és egy felhasználói beszámoló szerint nagy képeknél a modell gyengébb, ezért a méretet is mérni kell.

**Tartalékmodell:** ha a GLM-OCR a saját blokkokon gyenge, a `qwen3-vl:4b` a tartalék, az `OLLAMA_MODEL` cseréjével. Ennél a `think: false`, a `/no_think` és a `format: json` nem kapcsolta ki a gondolkodást: 2200 token, azaz 269 másodperc után sem jött válasz. Asszisztens-üzenetként a `</think>\n\n{"store":` szöveget kell előre megadni, a válasz ennek a folytatása.

## FIN-304 Feltöltő képernyő · 5 SP

**Story:** felhasználóként egy képernyőn akarom feltölteni a blokkot, a vásárlóval, a dátummal és a címkékkel együtt, hogy a rögzítés ne legyen macerás.

**Részfeladatok**

- [ ] `GET /`: egy képernyős feltöltő oldal: fotó, ki vásárolt, a blokk dátuma, ki fizetett, egy vagy több címke 📅 2026-12-13
- [ ] A feltöltő felhasználó választható, az utolsó érték megmarad a böngészőben; a FIN-303 után a belépett felhasználó adja 📅 2026-12-13
- [ ] `POST /uploads` multipart kéréssel, `python-multipart==0.0.32` függőséggel 📅 2026-12-13
- [ ] Alapértékek: a vásárló a feltöltő, a dátum a mai nap, a fizető fél `shared` 📅 2026-12-13
- [ ] A feltöltés ideje a szerveren áll be, a kliens nem adhatja meg 📅 2026-12-13
- [ ] Validálás a lenti szabályok szerint, a fájl típusát a tartalma alapján 📅 2026-12-13
- [ ] A fájl változatlanul kerül a postaládába, mellé SHA-256 hash 📅 2026-12-13
- [ ] `manifest.webmanifest` a későbbi telefonos telepítéshez 📅 2026-12-13
- [ ] pytest-tesztek kódból generált képekkel, a Pillow csak fejlesztői függőség 📅 2026-12-13

**Elfogadási feltételek**

- [ ] Böngészőből egy képernyőn feltölthető
- [ ] A feltöltött fájl bájtra azonos az eredetivel
- [ ] Hibás típusra, túl nagy fájlra és érvénytelen mezőre 4xx válasz jön, és a postaláda nem változik
- [ ] A feltöltés ideje akkor is a szerveré, ha a kliens küld ilyen mezőt
- [ ] A webapp portja továbbra is csak a `127.0.0.1` címen figyel

**Validálási szabályok**

| Mező | Szabály |
| --- | --- |
| `file` | JPEG, PNG, HEIC vagy WebP, legfeljebb 20 MB |
| `uploaded_by` | A `HOUSEHOLD_MEMBERS` egyik értéke |
| `purchased_by` | A `HOUSEHOLD_MEMBERS` egyik értéke, alapból a feltöltő |
| `purchase_date` | Kötelező dátum, nem lehet jövőbeli |
| `payer` | `shared` vagy a `HOUSEHOLD_MEMBERS` egyik értéke, alapból `shared` |
| `tags` | Legalább egy alap kategória; a címke a blokkra vonatkozik, ezért több is lehet |

## FIN-305 Postaláda API a workernek · 3 SP

**Story:** fejlesztőként olyan postaládát akarok, amelyből a worker húzza le a feltöltéseket, hogy minden kapcsolatot az otthoni oldal nyisson, és a Pi-re költözéskor ne kelljen a folyamatot átírni.

**Részfeladatok**

- [ ] SQLite postaláda a `data/inbox` mappában, a fájlok mellett; a konténer `nobody` felhasználója is írhassa 📅 2026-12-13
- [ ] `GET /inbox/items?status=new`: a feldolgozandó tételek 📅 2026-12-13
- [ ] `GET /inbox/items/{id}/file`: a fájl letöltése 📅 2026-12-13
- [ ] `POST /inbox/items/{id}/close`: lezárás, a fájl törlése; ismételt hívásra is sikeres 📅 2026-12-13
- [ ] Minden `/inbox` végpont `Authorization: Bearer` tokent kér, a `WORKER_API_TOKEN` az `init-env.sh`-ból jön 📅 2026-12-13
- [ ] A postaláda írása egyetlen modulban legyen, a meglévő `store.py` mintájára 📅 2026-12-13
- [ ] pytest-tesztek a végpontokra és a jogosultságra 📅 2026-12-13

**Elfogadási feltételek**

- [ ] Token nélkül vagy rossz tokennel 401 jön
- [ ] A lezárt kép eltűnik a postaládából
- [ ] Egy lezárt tétel ismételt lezárása nem hiba
- [ ] A webapp újraindítása után a nyitott tételek megvannak
- [ ] A postaláda adatai nem kerülnek a repóba

**Postaláda tábla: `inbox_item`**

| Mező | Megjegyzés |
| --- | --- |
| `id` | UUID |
| `sha256` | A fájl hash-e |
| `filename`, `content_type`, `size_bytes` | A feltöltött fájl adatai |
| `uploaded_by`, `uploaded_at` | Ki és mikor; az idő UTC |
| `purchased_by`, `purchase_date`, `payer`, `tags` | A feltöltéskor megadott adatok |
| `status` | `new` vagy `closed` |
| `closed_at` | Lezárás ideje |

A lezárás a 3. sprintben a bronz rekord után történik. A FIN-405-tel a jóváhagyás utánra kerül, mert az Ellenőrzés képernyőnek is kell a kép.

## FIN-306 Worker: Garage, duplikációszűrés, bronz rekord · 5 SP

**Story:** adatgazdaként azt akarom, hogy minden feltöltés pontosan egyszer, változatlanul kerüljön a Garage-ba és a bronzba, akkor is, ha a folyamat közben leáll.

**Részfeladatok**

- [ ] `worker/` Python szolgáltatás Dockerfile-lal: `httpx==0.28.1`, `boto3==1.43.123`, `psycopg[binary]==3.3.6` 📅 2026-12-13
- [ ] `worker` szolgáltatás a Compose-ban, `app_writer`-ként, `restart: unless-stopped` 📅 2026-12-13
- [ ] Ciklus `WORKER_POLL_SECONDS` időközönként, alapból 60 másodperc, egyszerre egy tétellel 📅 2026-12-13
- [ ] Lépések a lenti sorrendben; bármelyik után újraindítható 📅 2026-12-13
- [ ] Letöltés után a hash ellenőrzése; eltérésnél a tétel nyitva marad, és hiba kerül a naplóba 📅 2026-12-13
- [ ] Tárolás a `raw` bucketben, `photo/ÉÉÉÉ/HH/<sha256>.<kiterjesztés>` kulccsal 📅 2026-12-13
- [ ] Bronz rekord `source_type = photo` értékkel, `on conflict (sha256) do nothing` beszúrással 📅 2026-12-13
- [ ] pytest-tesztek valódi Garage-dzsal és Postgresszel: a Garage-tesztobjektum törlődik, a bronz írás visszagörget 📅 2026-12-13
- [ ] CI-lépés: `scripts/test-worker.sh`, a Garage elindításával 📅 2026-12-13
- [ ] README: a teljes út a feltöltéstől a bronzig 📅 2026-12-13

**Elfogadási feltételek**

- [ ] A kétszer feltöltött kép egyszer kerül a bronzba, és mindkét postaláda-tétel lezárul
- [ ] A Garage-ban lévő fájl hash-e egyezik az eredetivel
- [ ] A bronz rekordban a feltöltő, a vásárló, a fizető fél, a dátum és a címkék megvannak
- [ ] A lezárás előtt leállított worker újraindítás után befejezi a munkát, nem vész el kép, és nincs duplikátum
- [ ] Ha a Garage nem érhető el, a tétel a postaládában marad
- [ ] A `dbt build` zöld marad a `raw_document` sorokkal

**A feldolgozás lépései**

1. Az új tételek lekérése a postaládából.
2. A fájl letöltése és a hash ellenőrzése.
3. Feltöltés a Garage-ba; ugyanaz a kulcs ugyanazt a tartalmat kapja.
4. Bronz rekord beszúrása; ha a hash már megvan, nem történik semmi.
5. A postaláda-tétel lezárása.

## Események és nyitott kérdések

- [ ] Sprinttervezés, kb. 30 perc 📅 2026-11-30
- [ ] Heti áttekintés, kb. 15 perc 📅 2026-12-07
- [ ] Demó és retró, kb. 30 perc 📅 2026-12-13
- [ ] Kiadás: `v0.3.0` a [[Release folyamat]] szerint 📅 2026-12-13

**Eldöntve a tervezés előtt**

- [x] A blokkbeolvasás a Pi elé kerül, a Pi a 6. sprintben jön, az első éles használat dátuma marad ([[0006-blokkbeolvasas-a-pi-elott|ADR 0006]]).
- [x] A modell egyelőre a laptopon, CPU-n fut; a `glm-ocr` az alapmodell, a `qwen3-vl:4b` a tartalék.

**A tervezésen eldöntendő**

- [ ] Mikortól kerülhet valódi blokk a helyi rendszerbe? A kinyerés pontossága kitalált blokkon nem mérhető, a FIN-402 és a FIN-407 saját blokkokat kér. Javaslat: a 4. sprinttől mehet, csak helyben, a repón kívül; a FIN-309 törli őket. 📅 2026-11-30
