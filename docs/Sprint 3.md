---
projekt: Pénzügyi nyomkövető
sprint: S3
kezdes: 2026-11-30
vege: 2026-12-13
story_pont: 23
tags: [penzugy, sprint]
---

# Sprint 3

Vissza: [[Fejlesztési terv]]

## Sprint cél

**Egy böngészőből feltöltött blokkfotó a helyi postaládán át a Garage-ba és a bronzba kerül, a laptopon futó GLM-OCR kiolvasása is a bronzba kerül, és a stack minden része egy weboldalon követhető.** A sprint 2026-11-30 és 2026-12-13 között tart, 23 story ponttal.

| Kulcs | Jegy | SP | Függ tőle |
| --- | --- | --- | --- |
| FIN-401 | Ollama és GLM-OCR a laptop CPU-ján | 2 | — |
| FIN-304 | Feltöltő képernyő | 5 | FIN-203 |
| FIN-305 | Postaláda API a workernek | 3 | FIN-304 |
| FIN-306 | Worker: Garage, duplikációszűrés, bronz rekord | 5 | FIN-102, FIN-201, FIN-305 |
| FIN-408 | Kiolvasás a workerben | 3 | FIN-401, FIN-306 |
| FIN-106 | Állapot képernyő | 5 | FIN-305, FIN-306, FIN-408 |

Javasolt sorrend: először a FIN-401, utána a FIN-304, a FIN-305, a FIN-306 és a FIN-408, végül a FIN-106. A modell már ebben a sprintben a workerbe kerül, mert a saját blokkokon ez ad először valódi eredményt. Az eredmény ellenőrzése és normalizálása a FIN-402-vel és a FIN-404-gyel, a 4. sprintben jön.

**Helyi postaláda:** a Pi a 6. sprintben jön, de a postaláda API már most elkészül, helyben futtatva. A worker így a költözéskor csak egy másik címre mutat ([[0006-blokkbeolvasas-a-pi-elott|ADR 0006]]). A telefon addig nem éri el a webappot, a feltöltés böngészőből történik.

**Adat:** a tesztek blokkjai kódból készülnek, képfájl nem kerül a repóba. Saját próbablokk csak helyben, a böngészőből kerülhet a rendszerbe. A bronz és a Garage tartalma az első éles használat előtt üresen újraépül (FIN-309).

## FIN-401 Ollama és GLM-OCR a laptop CPU-ján · 2 SP

**Story:** fejlesztőként a laptopon akarom futtatni a képfelismerő modellt, hogy a blokkbeolvasás a főgép és a Pi nélkül is fejleszthető legyen.

**Részfeladatok**

- [x] `ollama` szolgáltatás a Compose-ban: `docker.io/ollama/ollama:0.40.13`, `restart: unless-stopped`, port nélkül 📅 2026-12-13
- [x] Modellek a `data/ollama` mappában, így újraindítás után nem töltődnek le újra 📅 2026-12-13
- [x] `scripts/ollama-pull.sh`: a `glm-ocr` letöltése, a modell azonosítójának kiírása 📅 2026-12-13
- [x] `OLLAMA_MODEL` és `OLLAMA_NUM_THREAD` a `.env.example`-ben, alapból `glm-ocr` és 10 📅 2026-12-13
- [x] `worker/tools/smoke_receipt.py`: kódból rajzolt, kitalált blokkot küld a modellnek, és ellenőrzi a kimenetet 📅 2026-12-13
- [x] README: a modell letöltése és a futási idő a laptopon 📅 2026-12-13

**Elfogadási feltételek**

- [x] Egy kitalált mintablokkra érvényes JSON jön vissza, 1 percen belül
- [x] A kimenet a `store`, `date`, `items` és `total` mezőket tartalmazza
- [x] A konténer újraindítása után a modell nem töltődik le újra
- [x] Az Ollama portja nem látszik a gazdagépen
- [x] A modell futása közben a stack szolgáltatásai egészségesek maradnak

**Mérés a laptopon**

2026-10-31-én, Ollama 0.40.13-mal, CPU-n, 10 szálon mérve. A minták számítógéppel rajzolt, kitalált blokkok, ezért a valódi, gyűrött fotókra nem bizonyítanak semmit; az időkre viszont lehet tervezni. Ez az első táblázat kis, kb. 600 pixel széles képekkel készült.

| Modell | Letöltés | Teljes idő | Kép feldolgozása | Válasz írása | Memória | Ezres tagolás |
| --- | --- | --- | --- | --- | --- | --- |
| `glm-ocr` | 2,7 GB | 17 mp | 10 mp | 5 mp | kb. 5 GB | helyes |
| `qwen3-vl:4b` | 3,3 GB | 56 mp | 41 mp | 12 mp | kb. 8 GB | hibás |
| `qwen3-vl:8b` | 6,2 GB | 92 mp | 69 mp | 19 mp | nincs külön mérve | hibás |

**A modell hívása**

| Beállítás | Érték | Miért |
| --- | --- | --- |
| Prompt | A kért JSON szerkezete, mintául | A GLM-OCR séma alapján nyer ki adatot |
| `format` | JSON-séma | Enélkül a modell néha vessző nélkül sorolta a tételeket; a `format: json` csak egy tételt adott |
| `num_thread` | 10 | Az Ollama alapból kb. 2 magot használt |
| `num_predict` | 2000 | Egy 30 tételes blokk kb. 750 token, 500-nál a JSON csonka maradt |
| `temperature` | 0 | A kinyerés legyen ismételhető |
| `keep_alive` | `0` | A modell a futás után felszabadítja a memóriát |

**Képméret**

Kitalált, fotószerű képeken mérve: 3000×4000 pixel, ferde, kissé életlen, zajos, asztali háttérrel. A méret a modellnek küldött kép hosszabb oldala; JSON módban, sémával.

| Méret | 5 tételes blokk | 30 tételes blokk | Jó árak | Jó végösszeg |
| --- | --- | --- | --- | --- |
| 1000 px | 33 mp | 51 mp | 5/5, 30/30 | nem, igen |
| 1400 px | 76 mp | 81 mp | 5/5, 29/30 | igen, igen |
| 2000 px | 203 mp | 167 mp | 4/5, nincs számolva | igen, igen |

Az alap 1400 px, mert 2000 px-nél 2,5-szer lassabb, és nem pontosabb. Az 1000 px nem biztonságos: a valódi fotón a blokk a képnek csak egy része, ezért a betűk kisebbek, mint a mintán. Ezt a saját fotókon mérni kell. 1000 és 1400 px-en a 30 tételes blokk 3 fölös sort is adott, amit a FIN-404-nek ki kell szűrnie.

**Tanulságok a FIN-402-höz**

- **Ékezetek:** az `Ő` többször `Ö` lett (`ŐSZIBARACK` helyett `ÖSZIBARACK`), a többi ékezetes betű helyes volt.
- **Fizetési mód:** JSON módban üres vagy hibás maradt, szöveges módban (`Text Recognition:`) a `SZÉP-KÁRTYA` sor is helyesen megjött.
- **Végösszeg:** JSON módban ugyanarra a blokkra `7626`, `6467`, `6043` és `626` is jött, a szöveges mód minden mintán helyes volt. A végösszeget ezért a szöveges olvasatból érdemes venni.
- **Dátum:** a blokkon lévő formában jön vissza, ezért `ÉÉÉÉ-HH-NN` alakra kell hozni.
- **Kimenet:** séma nélkül ```` ```json ```` jelölésben érkezik; a sémával nincs jelölés.
- **Kép:** a HEIC-et át kell alakítani, és az EXIF szerint el kell forgatni; ezt a FIN-408 már elvégzi.

**Tartalékmodell:** ha a GLM-OCR a saját blokkokon gyenge, a `qwen3-vl:4b` a tartalék, az `OLLAMA_MODEL` cseréjével. Ennél a `think: false`, a `/no_think` és a `format: json` nem kapcsolta ki a gondolkodást: 2200 token, azaz 269 másodperc után sem jött válasz. Asszisztens-üzenetként a `</think>\n\n{"store":` szöveget kell előre megadni, a válasz ennek a folytatása. Ezt a worker még nem tudja, a váltáskor kell megírni.

## FIN-304 Feltöltő képernyő · 5 SP

**Story:** felhasználóként egy képernyőn akarom feltölteni a blokkot, a vásárlóval, a dátummal és a címkékkel együtt, hogy a rögzítés ne legyen macerás.

**Részfeladatok**

- [x] `GET /`: egy képernyős feltöltő oldal: fotó, ki vásárolt, a blokk dátuma, ki fizetett, egy vagy több címke 📅 2026-12-13
- [x] A feltöltő felhasználó választható, az utolsó érték megmarad a böngészőben; a FIN-303 után a belépett felhasználó adja 📅 2026-12-13
- [x] `POST /uploads` multipart kéréssel, `python-multipart==0.0.32` függőséggel 📅 2026-12-13
- [x] Alapértékek: a vásárló a feltöltő, a dátum a mai nap, a fizető fél `shared` 📅 2026-12-13
- [x] A feltöltés ideje a szerveren áll be, a kliens nem adhatja meg 📅 2026-12-13
- [x] Validálás a lenti szabályok szerint, a fájl típusát a tartalma alapján 📅 2026-12-13
- [x] A fájl változatlanul kerül a postaládába, mellé SHA-256 hash 📅 2026-12-13
- [x] `manifest.webmanifest` a későbbi telefonos telepítéshez 📅 2026-12-13
- [x] pytest-tesztek kódból generált képekkel, a Pillow csak fejlesztői függőség 📅 2026-12-13

**Elfogadási feltételek**

- [x] Böngészőből egy képernyőn feltölthető
- [x] A feltöltött fájl bájtra azonos az eredetivel
- [x] Hibás típusra, túl nagy fájlra és érvénytelen mezőre 4xx válasz jön, és a postaláda nem változik
- [x] A feltöltés ideje akkor is a szerveré, ha a kliens küld ilyen mezőt
- [x] A webapp portja továbbra is csak a `127.0.0.1` címen figyel

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

- [x] SQLite postaláda a `data/inbox` mappában, a fájlok mellett; a konténer `nobody` felhasználója is írhassa 📅 2026-12-13
- [x] `GET /inbox/items?status=new`: a feldolgozandó tételek 📅 2026-12-13
- [x] `GET /inbox/items/{id}/file`: a fájl letöltése 📅 2026-12-13
- [x] `POST /inbox/items/{id}/close`: lezárás, a fájl törlése; ismételt hívásra is sikeres 📅 2026-12-13
- [x] Minden `/inbox` végpont `Authorization: Bearer` tokent kér, a `WORKER_API_TOKEN` az `init-env.sh`-ból jön 📅 2026-12-13
- [x] A postaláda írása egyetlen modulban legyen, a meglévő `store.py` mintájára 📅 2026-12-13
- [x] pytest-tesztek a végpontokra és a jogosultságra 📅 2026-12-13

**Elfogadási feltételek**

- [x] Token nélkül vagy rossz tokennel 401 jön
- [x] A lezárt kép eltűnik a postaládából
- [x] Egy lezárt tétel ismételt lezárása nem hiba
- [x] A webapp újraindítása után a nyitott tételek megvannak
- [x] A postaláda adatai nem kerülnek a repóba

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

A lezárás a 3. sprintben a kiolvasás után történik. A FIN-405-tel a jóváhagyás utánra kerül, mert az Ellenőrzés képernyőnek is kell a kép.

## FIN-306 Worker: Garage, duplikációszűrés, bronz rekord · 5 SP

**Story:** adatgazdaként azt akarom, hogy minden feltöltés pontosan egyszer, változatlanul kerüljön a Garage-ba és a bronzba, akkor is, ha a folyamat közben leáll.

**Részfeladatok**

- [x] `worker/` Python szolgáltatás Dockerfile-lal: `httpx==0.28.1`, `boto3==1.43.123`, `psycopg[binary]==3.3.6`, `pillow==13.0.0`, `pillow-heif==1.8.1` 📅 2026-12-13
- [x] `worker` szolgáltatás a Compose-ban, `app_writer`-ként, `restart: unless-stopped` 📅 2026-12-13
- [x] Ciklus `WORKER_POLL_SECONDS` időközönként, alapból 60 másodperc, egyszerre egy tétellel 📅 2026-12-13
- [x] Lépések a lenti sorrendben; bármelyik után újraindítható 📅 2026-12-13
- [x] Letöltés után a hash ellenőrzése; eltérésnél a tétel nyitva marad, és hiba kerül a naplóba 📅 2026-12-13
- [x] Tárolás a `raw` bucketben, `photo/ÉÉÉÉ/HH/<sha256>.<kiterjesztés>` kulccsal 📅 2026-12-13
- [x] Bronz rekord `source_type = photo` értékkel, `on conflict (sha256) do nothing` beszúrással 📅 2026-12-13
- [x] pytest-tesztek valódi Garage-dzsal és Postgresszel: a Garage-tesztobjektum törlődik, a bronz írás visszagörget 📅 2026-12-13
- [x] CI-lépés: `scripts/test-worker.sh`, a Garage elindításával 📅 2026-12-13
- [x] README: a teljes út a feltöltéstől a bronzig 📅 2026-12-13

**Elfogadási feltételek**

- [x] A kétszer feltöltött kép egyszer kerül a bronzba, és mindkét postaláda-tétel lezárul
- [x] A Garage-ban lévő fájl hash-e egyezik az eredetivel
- [x] A bronz rekordban a feltöltő, a vásárló, a fizető fél, a dátum és a címkék megvannak
- [x] A lezárás előtt leállított worker újraindítás után befejezi a munkát, nem vész el kép, és nincs duplikátum
- [x] Ha a Garage nem érhető el, a tétel a postaládában marad
- [x] A `dbt build` zöld marad a `raw_document` sorokkal

**A feldolgozás lépései**

1. Az új tételek lekérése a postaládából.
2. A fájl letöltése és a hash ellenőrzése.
3. Ha a hash már a bronzban van, a 4. és az 5. lépés kimarad.
4. Feltöltés a Garage-ba; ugyanaz a kulcs ugyanazt a tartalmat kapja.
5. Bronz rekord beszúrása.
6. Kiolvasás, ha ehhez a modellváltozathoz még nincs (FIN-408).
7. A postaláda-tétel lezárása.

## FIN-408 Kiolvasás a workerben · 3 SP

**Story:** felhasználóként azt akarom, hogy a feltöltött blokkot a modell kiolvassa, hogy a saját blokkjaimon lássam, mire képes.

**Részfeladatok**

- [x] A kép előkészítése: EXIF szerinti forgatás, HEIC átalakítás, 1400 px-es JPEG; az eredeti a Garage-ban változatlan marad 📅 2026-12-13
- [x] Két olvasat ugyanarról a képről: JSON séma szerint és szövegként 📅 2026-12-13
- [x] `bronze.extraction` sor a modell nevével, azonosítójával és a prompt verziójával 📅 2026-12-13
- [x] Hibakezelés a lenti táblázat szerint 📅 2026-12-13
- [x] `scripts/last-extraction.sh` a legutóbbi kiolvasás megtekintéséhez 📅 2026-12-13
- [x] pytest-tesztek csonk modellel, a kép előkészítésére és a hibákra 📅 2026-12-13
- [x] README: a kiolvasás megtekintése és a várható idő 📅 2026-12-13

**Elfogadási feltételek**

- [x] Egy feltöltött JPEG és HEIC kiolvasása bekerül a `bronze.extraction` táblába
- [x] A sor tartalmazza a modell azonosítóját és a prompt verzióját
- [x] Ugyanarra a képre ugyanazzal a modellváltozattal nem fut le újra a modell
- [x] Ha az Ollama nem érhető el, a tétel nyitva marad, a nyers kép pedig már a Garage-ban és a bronzban van
- [x] A rossz kimenet is a bronzba kerül, és a tétel lezárul, így nem fut újra percenként
- [x] A naplóban nincs blokktartalom, csak a tétel azonosítója

**Mérés a teljes úton**

2026-10-31-én, 1400 px-es bemenettel, a két olvasat együtt: egy 5 tételes fotószerű JPEG 145 másodperc, egy 30 tételes HEIC 216 másodperc. Mindkettőnél helyes lett a végösszeg és a szöveges olvasat, csak az `Ő` lett `Ö`. A kitalált, kis mintablokk 33 másodperc.

**Hibák kezelése**

| Hiba | A tétel | A bronzba kerül |
| --- | --- | --- |
| Az Ollama nem érhető el, vagy hibát ad | Nyitva marad, a worker újrapróbálja | Csak a nyers kép |
| A modell nincs letöltve | Nyitva marad, a napló a `scripts/ollama-pull.sh`-ra mutat | Csak a nyers kép |
| A kimenet nem érvényes JSON | Lezárul | `parsed: null`, a nyers szöveg megmarad |
| A kép nem olvasható | Lezárul | `error` mező |

**A `payload` mezői**

| Mező | Tartalom |
| --- | --- |
| `raw_text` | A JSON módú válasz, változatlanul |
| `parsed` | Ugyanez feldolgozva, vagy `null` |
| `ocr_text` | A szöveges olvasat |
| `done_reason` | A JSON mód leállási oka; a `length` csonka kimenetet jelez |
| `seconds` | A két olvasat együttes ideje |
| `error` | Csak akkor van, ha a kép nem olvasható |

## FIN-106 Állapot képernyő · 5 SP

**Story:** a rendszer gazdájaként egy weboldalon akarom látni a stack minden részét és a feldolgozást, hogy parancsok nélkül tudjam, mi fut, mi hibás, és épp mit csinál a modell.

**Részfeladatok**

- [x] `GET /status`: egy képernyős oldal a lenti kártyákkal, 5 másodpercenként frissül az oldal újratöltése nélkül 📅 2026-12-13
- [x] `GET /status.json`: az összesített állapot; a feltöltő oldalról link vezet a `/status`-ra 📅 2026-12-13
- [x] `POST /inbox/status/{source}`: `host` és `worker` jelentés a `WORKER_API_TOKEN` tokennel 📅 2026-12-13
- [x] `status_report` SQLite-tábla: forrásonként csak a legutóbbi jelentés, előzmény nélkül 📅 2026-12-13
- [x] `POST /inbox/items/{id}/close` opcionális eredménnyel: `result`, `seconds`, `items`, az `inbox_result` táblába 📅 2026-12-13
- [x] Worker: jelentés minden lépésváltáskor és külön szálon 15 másodpercenként, az Ollama `/api/ps` és `/api/tags` adataival 📅 2026-12-13
- [x] Worker healthcheck: a jelentő szál által frissített fájl nem lehet 60 másodpercnél régebbi 📅 2026-12-13
- [x] `scripts/status-report.sh`: szolgáltatások, Garage-méret, sorszámok, timerek, lemez, memória, terhelés 📅 2026-12-13
- [x] `finance-status.timer` 15 másodpercenként, az `install-timers.sh` telepíti 📅 2026-12-13
- [x] pytest-tesztek a végpontokra, a jogosultságra, az elavulásra és az összképre 📅 2026-12-13
- [x] README: az oldal címe és a kártyák jelentése 📅 2026-12-13

**Elfogadási feltételek**

- [x] A `/status` a lenti kilenc kártyát mutatja, mindegyik saját állapottal
- [x] Feldolgozás alatt látszik a lépés neve és az eltelt idő, a modell pedig betöltve látszik
- [x] Egy leállított `ollama` vagy `worker` 30 másodpercen belül hibaként látszik
- [x] Hibás dbt-futás vagy mentés a kártyáján hibaként látszik, a következő futás idejével
- [x] 60 másodpercnél régebbi jelentésnél a kártya szürke, „nincs friss adat” felirattal, és soha nem zöld
- [x] Az oldalon és a `/status.json`-ban nincs fájlnév, blokktartalom vagy titok
- [x] Ha az állapotjelentés nem megy át, a feltöltés és a feldolgozás zavartalanul fut tovább
- [x] A `status-report.sh` tokenje nem látszik a folyamatlistában
- [x] A webapp portja továbbra is csak a `127.0.0.1` címen figyel

**Az oldal vázlata**

```text
Stack állapota                        Feldolgozás fut · frissült 3 mp-e

Szöveges olvasat · 1 p 12 mp · várakozik: 1 blokk

Feltöltés   ●  Worker     ●  Ollama    ●
Garage      ●  Postgres   ●  Metabase  ●
dbt         ●  Mentés     ●  Gép       ●

Legutóbbi feldolgozások
15:37   145 mp   rendben   4 tétel
```

**Kártyák**

| Kártya | Mit mutat | Honnan jön |
| --- | --- | --- |
| Feltöltés | Egészség, várakozó és lezárt tételek | `compose ps`, postaláda |
| Worker | Aktuális lépés, eltelt idő, utolsó jelentés | Worker-jelentés, `compose ps` |
| Ollama | Modell neve, azonosítója, betöltve van-e, memóriája | `/api/ps`, `/api/tags`, `compose ps` |
| Garage | Objektumok száma és mérete | `garage bucket info raw`, `compose ps` |
| Postgres | Sorok száma bronzban, silverben, goldban | `row_counts`, `compose ps` |
| Metabase | Egészség, link a dashboardokra | `compose ps` |
| dbt | Utolsó futás, eredmény, következő futás | `systemctl --user` |
| Mentés | Utolsó futás, eredmény, következő futás | `systemctl --user` |
| Gép | Szabad lemez, szabad memória, terhelés | `df`, `/proc` |

Az adatok lekérdezése 2026-10-31-én egyenként 0,1 másodpercen belül volt, ezért a 15 másodperces jelentés nem terheli a gépet.

**Összkép**

| Felirat | Mikor |
| --- | --- |
| Hiba | Egy szolgáltatás nem fut vagy `unhealthy`, a modell nincs letöltve, vagy az utolsó dbt-futás vagy mentés hibás |
| Nincs friss adat | A `host` vagy a `worker` jelentés 60 másodpercnél régebbi |
| Feldolgozás fut | A worker tételen dolgozik |
| Várakozik | Van nyitott tétel, a worker a következő körre vár |
| Minden rendben | Egyik sem igaz |

**Feldolgozási lépések**

A worker ezeket jelenti: `idle`, `download`, `storage`, `read_json`, `read_text`, `close`. A modell hívása percekig blokkol, ezért a jelentő szál külön fut, és saját HTTP-klienst használ. A tétel eredménye `ok`, `unparsed`, `unreadable` vagy `duplicate`.

Nincs riasztás és nincs előzmény: az oldal a pillanatnyi állapotot mutatja, a naplók továbbra is a `podman compose logs` paranccsal olvashatók. Ha a webapp nem fut, az oldal sem nyílik meg. A döntés indoka: [[0008-allapot-kepernyo-a-webappban|ADR 0008]].

## Események és nyitott kérdések

- [ ] Sprinttervezés, kb. 30 perc 📅 2026-11-30
- [ ] Heti áttekintés, kb. 15 perc 📅 2026-12-07
- [ ] Demó és retró, kb. 30 perc 📅 2026-12-13
- [x] Kiadás: `v0.3.0` a [[Release folyamat]] szerint 📅 2026-12-13

**Eldöntve a tervezés előtt**

- [x] A blokkbeolvasás a Pi elé kerül, a Pi a 6. sprintben jön, az első éles használat dátuma marad ([[0006-blokkbeolvasas-a-pi-elott|ADR 0006]]).
- [x] A modell egyelőre a laptopon, CPU-n fut; a `glm-ocr` az alapmodell, a `qwen3-vl:4b` a tartalék.

- [x] Saját próbablokk már a 3. sprinttől a helyi rendszerbe kerülhet, a repón kívül, és a FIN-309 törli. A kiolvasás pontossága kitalált blokkon nem mérhető.
