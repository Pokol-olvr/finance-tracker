# Pénzügyi nyomkövető

Kétszemélyes háztartási pénzügyi nyomkövető medallion adatrétegekkel és helyi blokkbeolvasással. A tervek a `docs/` mappában vannak: [Üzleti koncepció](docs/Üzleti%20koncepció.md), [Technikai terv](docs/Technikai%20terv.md), [Fejlesztési terv](docs/Fejlesztési%20terv.md).

A jelenlegi állapot az otthoni stack: Postgres a bronz, silver és gold sémákkal, Garage object store, kézi bejegyzés API és blokkfeltöltés, a GLM-OCR kiolvasásával, dbt és Streamlit riportok, napi mentéssel, és egy állapot képernyő a stack minden részéről. Egyelőre minden helyben fut, mock adattal és néhány saját próbablokkal.

## Előfeltételek

- Rootless Podman, a `scripts/setup-podman.sh` egyszeri beállításával (Fedora); a CI Dockert használ, az is működik
- Windowson WSL2-es Ubuntu Docker Engine-nel, a `scripts/setup-wsl.sh` egyszeri beállításával (lásd [Windows és WSL](#windows-és-wsl))
- `openssl`, `curl`, `jq`
- 5 GB szabad memória a kiolvasás idejére
- 3 GB szabad lemez a modellnek

## Gyorsindítás

```sh
git clone <repo-url> finance-tracker && cd finance-tracker
scripts/setup-podman.sh
scripts/init-env.sh
scripts/ollama-pull.sh
podman compose -f home/docker-compose.yml up -d --build
```

A riportok a `http://127.0.0.1:8501` címen érhetők el. A feltöltés, az Ellenőrzés, a szabályok és a betétdíj a `http://127.0.0.1:8000` címen van.

A `scripts/init-env.sh` által generált `RESTIC_PASSWORD` értékét mentsd el a jelszókezelőbe, nélküle a mentés használhatatlan.

### Windows és WSL

Windowson a stack a WSL2-es Ubuntuban fut, Docker Engine-nel. A repót a WSL saját fájlrendszerébe kell klónozni, nem a `C:` meghajtóra: ott a Git CRLF sorvégekkel bontja ki a scripteket, és a bind mountok lassúak. A szerkesztéshez a VS Code WSL-bővítménye vagy a `\\wsl$` út használható.

```sh
git clone <repo-url> ~/repos/finance-tracker && cd ~/repos/finance-tracker
scripts/setup-wsl.sh
newgrp docker
scripts/init-env.sh
scripts/ollama-pull.sh
docker compose -f home/docker-compose.yml up -d --build
scripts/dbt.sh
```

A `scripts/setup-wsl.sh` systemd-t vár, ezt a `/etc/wsl.conf` `[boot]` részében a `systemd=true` kapcsolja be. A portok a WSL-ből a Windows `127.0.0.1` címére is kijönnek, így a böngésző a fenti címeken éri el őket. A timerek csak akkor futnak, ha a WSL fut: nyitott WSL-ablak nélkül a Windows egy idő után leállítja.

A Docker konténerei rootként futnak, ezért a `home/data` törléséhez `sudo rm -rf home/data` kell a `podman unshare` helyett.

NVIDIA GPU-val a kiolvasás a GPU-n fut. A `scripts/setup-wsl-gpu.sh` telepíti az NVIDIA container toolkitet, a `home/.env`-ben pedig a `COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml` kapcsolja be. Ilyenkor a modell 10 percig betöltve marad (`OLLAMA_KEEP_ALIVE`), mert a blokkonkénti újratöltés CPU-n tovább tart, mint maga a kiolvasás. A kép hosszabb oldala 2000 pixel (`OLLAMA_MAX_SIDE`, CPU-n 1400), mert a saját blokkokon a számjegyhibát ez kijavította. A modell egy CPU-szálat kap (`OLLAMA_NUM_THREAD`), mert több szál a GPU-ra várva is pörög: 17 blokkon 1, 2, 4 és 10 szállal is 36–40 másodperc volt a modellidő, a CPU-használat viszont 97% és 536% között változott. Egy RTX 5070-en 17 blokk 94 másodperc alatt olvasódott ki újratöltéssel.

### Postaláda a Pi-n

A webapp a Raspberry Pi 4-en fut, Caddy és Authelia mögött, csak a Tailscale-hálózatról elérhetően. A feldolgozó az otthoni gép marad: minden kapcsolatot ez nyit a Pi felé. A Pi-n nincs adatbázis, a kézi bejegyzés API-ja (`/entries`) ott 503-at ad, amíg a FIN-606 a kimenő soron át nem viszi.

1. **A Pi-n** (64 bites Raspberry Pi OS): a repó klónozása, majd a Docker és a Tailscale telepítése a gyártók saját tárolójából, ha még nincs fent. A script a végén kiírja a Pi Tailscale-címét.
   ```sh
   scripts/setup-pi.sh
   ```
2. **DNS:** a `scripts/pi/pihole-tailnet.sh` a Pi-hole webszerverét a helyi címre szűkíti, hogy a Tailscale-cím 80-as és 443-as portja a Caddyé legyen, a `FINANCE_DOMAIN`, az `auth.` aldomain és a Vaultwarden nevét helyi rekordként a Pi Tailscale-címére irányítja, és a Pi-t leválasztja a Tailscale DNS-éről. A Tailscale admin felületén a domainre split DNS kell, a Pi Tailscale-címével. A Cloudflare-ben nincs rekord, ott csak egy API-token kell ehhez a zónához, `Zone.DNS` szerkesztési joggal, a tanúsítványhoz.
3. **Beállítások és felhasználók** a Pi-n; a felhasználónevek a `HOUSEHOLD_MEMBERS` kódjai, a jelszót az Authelia kéri be:
   ```sh
   scripts/init-pi-env.sh
   scripts/authelia-user.sh person_a
   scripts/authelia-user.sh person_b
   docker compose -f pi/docker-compose.yml up -d --build
   ```
4. **Első belépés:** a böngésző a TOTP beállítását kéri; a megerősítő kód a `pi/data/authelia/notification.txt` fájlba kerül, mert levél nincs.
5. **Az otthoni gépen** a `home/.env`-ben az `INBOX_URL` és a `STATUS_URL` a `https://` + `FINANCE_DOMAIN` cím, a `BIND_ADDRESS` az otthoni gép Tailscale-címe, majd `docker compose -f home/docker-compose.yml up -d`.
6. **Windowson** a WSL-nek ablak nélkül is futnia kell, és a portjainak a Tailscale-címen is látszaniuk kell; a script egy bejelentkezéskor induló feladatot és tükrözött hálózatot állít be, utána `wsl --shutdown`:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\windows\wsl-autostart.ps1
   ```
7. **Telefonokon** a Tailscale alkalmazás, majd a `FINANCE_DOMAIN` megnyitása és hozzáadása a kezdőképernyőhöz.

#### A Pi megerősítése

A Pi a háztartás DNS-szervere is (natív Pi-hole v6 és Unbound), ezért minden lépésnek van visszaútja. A routeren nincs és nem is kell port forward: a Tailscale NAT mögül is kapcsolódik, az otthoni gép nyit minden kapcsolatot, a tanúsítvány DNS-alapú. A scriptek a `scripts/pi/` mappában vannak, sorrendben, rendszergazdaként futtatva:

| Lépés | Mit csinál | Visszavonás |
| --- | --- | --- |
| `harden-1-fail2ban.sh <feldolgozó gép IP>` | fail2ban az SSH-ra: 10 percen belül 5 hiba után 1 óra tiltás; kivétel csak a Pi és a feldolgozó gép. Automatikus biztonsági frissítés, újraindítás nélkül | a script elején |
| `harden-2-limited-user.sh <felhasználó> <rendszergazda> '<kulcs>'` | Korlátozott felhasználó saját kulccsal: belép és olvas, de nincs `sudo`, nincs `docker` csoport, nincs jelszó; a rendszergazda mappáját nem látja | `userdel -r` |
| `harden-3-ssh.sh <rendszergazda> <korlátozott>` | SSH csak kulccsal, root nélkül, csak a két felhasználónak; a korlátozott nem építhet alagutat | a beállításfájl törlése |
| `harden-4-ufw.sh <helyi hálózat>` | Tűzfal: a helyi hálózatról DNS, NTP, SSH, a Pi-hole felülete, mDNS és a Beszel; a tailnetről DNS, SSH és a Caddy; minden más tiltva. Élesítéskor 5 perces önvisszavonó időzítő indul | `ufw disable` |
| `harden-4-finalize.sh` | Ellenőrzés után leállítja az időzítőt | – |

A harmadik lépés előtt mindkét felhasználó kulcsos belépését ki kell próbálni. A tűzfal a Docker által közzétett portokra nem vonatkozik, ezért a `pi/` Compose minden portot csak a Tailscale-címre köt.

Belépéssel a feltöltő és a döntést hozó mindig a belépett felhasználó: a webapp az Authelia `Remote-User` fejlécét veszi, és más nevében nem ment. A worker API (`/inbox/…`) és a `/health` belépés nélkül, a worker tokenjével érhető el.

## Felépítés

```text
home/        otthoni Compose, Postgres init, Garage config
pi/          a Pi Compose-fájlja, Caddy és Authelia (Sprint 6-tól)
webapp/      FastAPI webapp (Sprint 2-től)
reports/     riportok Streamlitben (Sprint 5-től)
worker/      lehúzás és kiolvasás (Sprint 3-tól)
dbt/         transzformációk (Sprint 2-től)
migrations/  bronz sémák SQL-migrációi
scripts/     mentés, visszaállítás, segédscriptek
docs/adr/    döntési jegyzetek
```

| Szolgáltatás | Cím | Feladat |
| --- | --- | --- |
| `postgres` | `127.0.0.1:5432` | `finance` adatbázis |
| `migrate` | nincs | Induláskor lefuttatja a `migrations/` mappát, majd kilép |
| `garage` | `127.0.0.1:3900` | S3 API, `raw` bucket |
| `inbox-init` | nincs | Induláskor beállítja a postaláda mappájának tulajdonosát, majd kilép |
| `webapp` | `127.0.0.1:8000` | Feltöltés, Ellenőrzés, Szabályok, Betétdíj és állapot képernyő, kézi bejegyzés API és postaláda; belépés nélkül, ezért csak helyben látszik |
| `ollama` | nincs | A GLM-OCR modell futtatója, csak a Compose-hálózaton |
| `worker` | nincs | A postaládából a Garage-ba és a bronzba viszi a feltöltéseket, és kiolvastatja őket |
| `reports` | `127.0.0.1:8501` | Riportok Streamlitben, csak a goldot olvassa; belépés nélkül, ezért csak helyben látszik |

Minden adat a `home/data/` alatt van, a helyét a `DATA_DIR` állítja. A riportok és a Garage címe a `BIND_ADDRESS` változóval a gép Tailscale-címére tehető. A Postgres mindig csak helyben látszik, a Garage admin és RPC portja pedig csak a Compose-hálózaton.

A konténerek rootless Podmanben a felhasználóhoz tartoznak, ezért a `home/data/postgres` törléséhez `podman unshare rm -rf home/data` kell. A `home/data/inbox` és a `home/data/ollama` nem kerül a mentésbe: az első átmeneti tároló, a második újra letölthető.

### Szerepkörök a `finance` adatbázisban

| Szerepkör | Jog | Ki használja |
| --- | --- | --- |
| `finance_owner` | A sémák tulajdonosa | Migrációk |
| `app_writer` | Beszúrás és olvasás a bronzban, olvasás a goldból | Webapp, worker |
| `dbt_runner` | Olvasás a bronzból, írás a silverbe és a goldba | dbt |
| `report_reader` | Csak olvasás a goldból | Riportok |

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

## Blokk és számla feltöltése és kiolvasása

A `http://127.0.0.1:8000` oldalon kell megadni a fájlokat, a feltöltőt, a vásárlót, a fizető felet és legalább egy címkét. Az oldal JPEG, PNG, HEIC, WebP vagy PDF fájlt fogad, fájlonként legfeljebb 20 MB-ig. A telefon a FIN-308-ig nem éri el az oldalt, ezért a fotót előbb a laptopra kell áttenni.

- **Több blokk egyszerre:** legfeljebb 20 fájl tölthető fel körönként, behúzással is. A megadott adatok mindegyikre érvényesek, és egy rossz fájl nem állítja meg a többit. Több fájlnál a dátum üres marad, és a dokumentumról olvassuk ki.
- **Egy dokumentum több fájlból:** az „Egy dokumentum több fájlból” kapcsolóval 2–5 kép vagy PDF tartozik egy dokumentumhoz, a nyilakkal rendezhető sorrendben. Így tölthető fel a hosszú blokk és az oldalanként külön fájlba szkennelt számla is. A két képen is látszó sorok egyszer számítanak. Ha bármelyik fájl hibás, egyik sem kerül be.
- **PDF:** a szöveges PDF modell nélkül, a szövegrétegéből olvasódik ki. A szkennelt PDF első 5 lapja képként a modellhez megy, lapjaként kb. másfél perc alatt. A jelszavas vagy sérült PDF „olvashatatlan” eredménnyel zár.

A worker percenként megnézi a postaládát, és tételenként végigviszi a folyamatot:

1. Letölti a fájlt, és ellenőrzi a hash-t.
2. Ha ez a fájl még nincs a bronzban, a `raw` bucketbe teszi `photo/ÉÉÉÉ/HH/<sha256>.<kiterjesztés>` vagy `pdf/ÉÉÉÉ/HH/<sha256>.pdf` kulccsal, és beírja a `bronze.raw_document` táblába.
3. Szöveggé olvastatja, és az eredményt a `bronze.extraction` táblába teszi. A szöveges PDF-hez itt nem kell modell, ilyenkor a `model_name` értéke `pdfium`.
4. A szöveg dönti el, hogy blokkról vagy számláról van szó. A saját feldolgozó ebből tételeket, végösszeget és fizetési adatokat készít, ellenőrzi őket, és az eredményt a `bronze.receipt_parse` táblába teszi.
5. Lezárja a tételt, a fájl ekkor törlődik a postaládából.
6. Az Ellenőrzés képernyőnek csomagot tölt vissza a webappba: a fájlt, a feldolgozott adatokat, az ellenőrzéseket és a szöveges olvasatot.

Ha az Ollama vagy a Garage nem érhető el, a tétel nyitva marad, és a worker a következő körben folytatja. A rossz kimenet is a bronzba kerül, és lezárja a tételt. A tételek sorban futnak. Az indoklás: [ADR 0009](docs/adr/0009-szabalyalapu-blokkfeldolgozo.md) és [ADR 0010](docs/adr/0010-pdf-olvasas-es-szamlafeldolgozo.md).

| Ellenőrzés | Szabály |
| --- | --- |
| `sum` | A tételek, a betétdíj, a kedvezmény és az utalvány összege a végösszeg |
| `line_total` | Mennyiség × egységár = érték, 1 Ft tűréssel; számlánál soronként nettó + áfa = bruttó is |
| `payment` | Fizetett − visszajáró = végösszeg, készpénznél 2 Ft tűréssel; a végösszeg alatti `GÖNGYÖLEG` sor DRS-utalvány, ezért fizetésnek számít |
| `date` | A beírt és a beolvasott dátum egyezik; a feltöltés napja nem számít beírt dátumnak, mert az űrlap azt kínálja fel |
| `duplicate` | Az adószám és a nyugta- vagy számlaszám máshol nem szerepel |
| `vat_summary` | Csak számlánál: az áfaösszesítő bruttója a végösszeg, 2 Ft tűréssel |
| `currency` | Csak számlánál: a végösszeg forintban van |

A dokumentum állapota `ok`, ha egyik ellenőrzés sem bukott el, `review`, ha valamelyik igen, és `unparsed`, ha nincs tétel vagy végösszeg. Egy ellenőrzés kimarad, ha hiányzik hozzá az adat. Az ismeretlen táblázatú számla `review` lesz a végösszeggel, és nem kap kitalált tételt. A szállítólevél, a díjbekérő és a proforma nem kiadás, ezért `unparsed` marad, és a `payload` `document_type` mezője `non_expense`. A számla kiadásának dátuma a teljesítés dátuma, a vevő neve és címe pedig csak a nyers szövegben marad.

A `worker/app/receipt_parser.py` és a `worker/app/invoice_parser.py` szabályai magyar formátumokra készültek. Új formátumhoz szabályt és kitalált tesztfájlt kell felvenni a `worker/tests/receipts/` vagy a `worker/tests/invoices/` mappába, majd növelni a `PARSER_VERSION` értékét. A worker induláskor a tárolt szövegeket modell nélkül újra feldolgozza.

### Ellenőrzés

A `http://127.0.0.1:8000/review` oldal listázza a dokumentumokat: elöl a döntésre várókat, utána az elmúlt 30 nap többi dokumentumát. Egy dokumentumot megnyitva balra az eredeti, jobbra a feldolgozott adatok látszanak, kiemelve az elbukott ellenőrzéseket. Keskeny képernyőn a kettő egymás alá kerül.

- **Jóváhagyom:** a feldolgozott adat így helyes.
- **Javítom:** a bolt, a dátum, a végösszeg és a tételek szerkeszthetők. A tételek összege legfeljebb 2 Ft-tal térhet el a végösszegtől.
- **Elvetem:** a dokumentum nem számít kiadásnak.

Döntést a `review`, az `unparsed` és az olvashatatlan dokumentum kér. Az `ok` és a nem kiadás dokumentum nem kér döntést, de megnyitható, és ha hibás, javítható vagy elvethető. Minden döntés visszavonható az Újranyitás gombbal, a korábbi döntés a bronzban megmarad.

Ami nem kiadás, például a szállítólevél, annál a képernyő ezt kiírja, és a szöveges olvasat nyitva látszik. Ilyenkor és ismeretlen táblázatú számlánál a szövegből kinyert sorok javaslatként jelennek meg. Ezek nem számítanak adatnak, amíg a javítást el nem mented.

A modell ugyanarra a fájlra ugyanazt adja, ezért nincs újraolvasó gomb: rossz fotónál új fotó kell, annak más a hash-e. Ha egy elvetett dokumentum fájlját töltöd fel újra, a dokumentum modellfutás nélkül újranyílik, minden más esetben az eredmény „már megvolt”. Kivétel a csonka olvasás: ha a modell kontextusa elfogyott, és azóta a beállítás változott, a worker induláskor újraolvassa a fájlt a Garage-ból ([ADR 0016](docs/adr/0016-csonka-olvasas-ujraolvasasa.md)). A kontextus 8192 token: a 2000 px-re kicsinyített kép a mérés szerint legfeljebb 4 112 képtoken (2000 × 2000-en), a szöveg legfeljebb 2 000. A feltöltött kép felbontása ezt nem növeli, mert a kép a modell előtt kicsinyül. Ha az olvasás mégis csonka, a worker azonnal újrapróbálja 16 384, majd 32 768 tokennel, kétszeres szöveghatárral, és a nagyobb modell utána kirakódik. A bronzban a `prompt_tokens`, a `num_ctx` és az `attempts` mutatja, mennyire volt közel a határ.

A döntés előbb a webappba kerül, innen a worker a következő körben a `bronze.review_decision` táblába írja, a `bronze.receipt_parse` nem változik. A javított érték a dbt következő futása után látszik a silverben és a riportokban. A csomag a döntésig marad, a lezárt dokumentumé 30 nap után törlődik a webappból, a fájl a Garage-ban megmarad. A 30 napnál régebbi `ok` dokumentumot a worker nem tölti vissza. A HEIC fájlt a böngésző nem jeleníti meg, ezért ott a worker JPEG-előnézetet küld. Az indoklás: [ADR 0011](docs/adr/0011-ellenorzes-kepernyo-csomagokkal.md) és [ADR 0012](docs/adr/0012-ujranyitas-az-ujraolvasas-helyett.md).

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

Egy repón kívüli mappa képei és PDF-jei a bronz érintése nélkül is kiolvashatók. Fájlonként egy `.txt` és egy `.json` fájl készül, megszakítás után a futás folytatható:

```sh
podman compose -f home/docker-compose.yml run --rm --no-deps --user 0 \
  -v "$HOME/blokk-mintak:/be:ro,z" -v "$HOME/blokk-eredmeny:/ki:z" \
  worker python -m tools.read_folder /be /ki
```

A kimenet nem kerülhet a repóba: a szöveges fájlokat a commit előtti ellenőrzés nem szűri.

A worker tesztjei a `scripts/test-worker.sh` paranccsal futnak, valódi Garage-dzsal és Postgresszel, a modellt egy csonk helyettesíti. A riportok tesztjei a `scripts/test-reports.sh` paranccsal futnak, kitalált adatokkal.

## Szabályok és betétdíj

A `http://127.0.0.1:8000/rules` oldalon vehetők fel a szabályok:

- **Tételszabály:** ha a tétel neve tartalmazza a mintát, a tétel megkapja a kategóriát. Az egyeztetés ékezet nélkül történik. Több találatnál a hosszabb minta nyer, egyezésnél a régebbi szabály.
- **Termékszabály:** ha a tétel neve tartalmazza a mintát, vagy a mintája a tétel EAN-je, a tétel megkapja a terméket, például `élelmiszer/gomba/csiperke`. A kategória a termékből jön, és a termékszabály erősebb a tételszabálynál. Több találatnál az EAN nyer, utána a hosszabb minta.
- **Kiszerelésszabály:** a kiszerelés nélküli névhez ad kiszerelést, például `SB BARNA CSIPERKE 500` → `500G`.
- **Boltszabály:** az adószámhoz egységes boltnév tartozik.

A szabály a régi dokumentumokra is érvényes, a kikapcsolt szabály a bronzban megmarad. Szabály nélkül az egy címkés blokk tétele a címkét kapja, a több címkésé `besorolatlan` lesz.

A silver minden tételhez alapegységet és egységárat számol: Ft/kg, Ft/l vagy Ft/db. A mérlegelt tételnél a mért mennyiség az alap, különben a darabszám és a névben vagy a szabályban álló kiszerelés, például `4X120G`. A tétel alatti kedvezmény csökkenti az egységárat. A `gold.product_prices` termékenként, boltonként és hónaponként adja a súlyozott egységárat. Az indoklás: [ADR 0015](docs/adr/0015-termekcsaladok-es-egysegar.md).

A `http://127.0.0.1:8000/deposit` oldal a várható DRS-betétdíjat mutatja. A blokkon fizetett betétdíj növeli, a beváltott utalvány csökkenti, egyik sem kiadás. Az összeg kézzel állítható és nullázható, a kézi művelet a következő dbt-futás után látszik. A negatív összeg azt jelzi, hogy régebbi vásárlás betétdíja nincs a rendszerben, ilyenkor egy kézi állítás adja a nyitó egyenleget. A nullázás a napra vonatkozik: az aznap vagy előtte kelt blokkok betétdíja elvész.

Mindkét oldal adata a webapp kimenő sorába kerül, innen a worker írja a bronzba. A várható összeget a worker tölti vissza a goldból, mert a webapp azt nem éri el.

## Riportok

A `http://127.0.0.1:8501` oldalon három riport van, a kód a `reports/` mappában:

- **Áttekintés:** bevétel, kiadás, egyenleg, megtakarítási ráta és várható betétdíj, a hónap összevetése az előzővel és az átlaggal, kiadás kategóriánként.
- **Kiadások:** a dokumentumok listája szűrhető arra, ki fizetett. Egy sor kiválasztása után a tételek látszanak termékkel és egységárral, a gomb pedig az Ellenőrzésre visz az eredetihez.
- **Árak:** egy termék legutóbbi és legolcsóbb egységára, a változás az első hónap óta, és havonta boltonként az ár. A termék a Szabályok oldalon felvett termékszabályból jön.

A kiadásba csak a rendben lévő, jóváhagyott vagy javított dokumentum számít, ezt egyedül a `silver.documents` dönti el ([ADR 0013](docs/adr/0013-beszamitas-a-silverben.md)). A dbt óránként fut, ezért a változás legfeljebb egy órán belül látszik.

A riport kizárólag a goldot olvassa, és csak olvasható kapcsolattal. A Streamlit használati statisztikája ki van kapcsolva, a `browser.serverAddress` beállítása pedig megakadályozza a nyilvános IP lekérdezését. Az indoklás: [ADR 0014](docs/adr/0014-streamlit-a-metabase-helyett.md).

## Állapot képernyő

A `http://127.0.0.1:8000/status` oldal tíz kártyán mutatja a stack részeit: Feltöltés, Worker, Ollama, Garage, Postgres, Riportok, dbt, Mentés, Gép és Erőforrások.

- **Ollama:** a modell mérete és kvantálása, hogy GPU-n vagy CPU-n fut és mennyi memóriát foglal, az utolsó olvasás ideje token/s sebességgel, valamint az utolsó 20 olvasás átlaga. Az átlag a bronzból töltődik vissza, ezért a worker újraindítása után sem üres.
- **Erőforrások:** a CPU minden szála külön oszlopban, a RAM és a swap, NVIDIA GPU-s gépen a GPU kihasználtsága, videomemóriája, hőmérséklete és fogyasztása.

Az erőforrás-adat 15 másodpercenkénti pillanatkép, a CPU egy másodperces mintából számol, ezért egy 2–3 másodperces olvasás csúcsa kimaradhat belőle. Fölöttük látszik az összkép és az aktuális feldolgozási lépés az eltelt idővel, alattuk a legutóbbi feldolgozások. Az oldal 5 másodpercenként frissül, az adatai a `/status.json` címen is elérhetők.

| Felirat | Jelentés |
| --- | --- |
| Hiba | Egy szolgáltatás nem fut vagy nem egészséges, a modell nincs letöltve, vagy az utolsó dbt-futás vagy mentés hibás |
| Nincs friss adat | Egy jelentés 60 másodpercnél régebbi, ezért a kártya szürke, nem zöld |
| Feldolgozás fut | A worker tételen dolgozik |
| Várakozik | Van nyitott tétel, a worker a következő körre vár |
| Minden rendben | Egyik sem igaz |

Az adatot két forrás küldi a webappnak, a `WORKER_API_TOKEN` tokennel. A `scripts/status-report.sh`-t a `finance-status.timer` 15 másodpercenként futtatja, ez jelenti a szolgáltatásokat, a timereket, a Garage és a Postgres adatait, a lemezt és a memóriát. A worker a lépéseit és az Ollama állapotát jelenti, külön szálon, mert a modell hívása percekig tart. A modell a betöltése alatt még `Betöltve: nem` állapotot mutat.

A „rendben” csak olyan blokkra jelenik meg, amelynek az ellenőrzései nem buktak el, az „Ellenőrzésre vár” szám a döntésre váró dokumentumokat mutatja, és a döntés után csökken. Az oldalon nincs fájlnév és blokktartalom, előzményt és riasztást nem tárol. Ha a webapp nem fut, az oldal sem nyílik meg, ekkor a `podman compose -f home/docker-compose.yml ps` marad. Az indoklás: [ADR 0008](docs/adr/0008-allapot-kepernyo-a-webappban.md).

## Migrációk

A migrációk sima SQL-fájlok a `migrations/` mappában, a [dbmate](https://github.com/amacneil/dbmate) futtatja őket. Az új fájl nevének eleje időbélyeg, és az alkalmazásukhoz elég újra lefuttatni a `migrate` szolgáltatást:

```sh
podman compose -f home/docker-compose.yml run --rm migrate
scripts/test-bronze.sh
```

A bronz csak hozzáfűzhető: az UPDATE, a DELETE és a TRUNCATE a tulajdonosnál is hibát ad. A javítás a silverben történik.

## Mentés

A `scripts/backup.sh` a futó stacken dolgozik:

1. `pg_dump` a `finance` adatbázisról a `home/backup/dumps/` mappába, a `finance` táblák sorszámával együtt.
2. A Garage `raw` bucket tükrözése a `home/backup/garage-raw/` mappába.
3. restic pillanatkép a `RESTIC_REPO_DIR` tárolóba, 7 napi, 4 heti és 6 havi megőrzéssel.

A `RESTIC_REPO_DIR` éles használatra külső meghajtóra mutasson; alapból ugyanazon a lemezen van, és a script erre figyelmeztet.

### Ütemezés

A systemd timerek óránként a `dbt build`-et, naponta 03:30-kor a mentést futtatják, és ha a gép ki volt kapcsolva, induláskor pótolják. A harmadik timer 15 másodpercenként az állapotjelentést küldi. A telepítés:

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
