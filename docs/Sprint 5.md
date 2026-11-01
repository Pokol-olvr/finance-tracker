---
projekt: Pénzügyi nyomkövető
sprint: S5
kezdes: 2026-12-28
vege: 2027-01-10
story_pont: 31
tags: [penzugy, sprint]
---

# Sprint 5

Vissza: [[Fejlesztési terv]]

## Sprint cél

**A rendben lévő és az eldöntött blokk vagy számla tételenként a silverbe kerül, a kiadások kategóriákra bomlanak, a DRS-betétdíj pedig külön, várható pénzként látszik. A riportok Streamlitben futnak, a Metabase kikerül.** A sprint 2026-12-28 és 2027-01-10 között tart, 31 story ponttal.

| Kulcs | Jegy | SP | Függ tőle |
| --- | --- | --- | --- |
| FIN-406 | Silver tétel szint | 8 | FIN-405, FIN-412 |
| FIN-206 | Streamlit riportfelület, a Metabase kivezetése | 8 | FIN-406 |
| FIN-501 | Címke- és boltszabályok | 5 | FIN-406 |
| FIN-409 | DRS-betétdíj külön vezetése | 5 | FIN-406 |
| FIN-407 | Mérés 20–30 saját blokkon | 2 | FIN-406, FIN-410 |
| FIN-403 | PaddleOCR második olvasat, feltételes | 3 | FIN-410 |

Javasolt sorrend: FIN-406, FIN-206, FIN-501, FIN-409, FIN-407. A FIN-406 kerül előre, mert a többi a tételekre épül. A FIN-206 megelőzi a szabályokat és a betétdíjat, hogy ezek már az új riportokban jelenjenek meg. A FIN-403 csak akkor indul, ha a FIN-410 mérése ezt kéri, különben a sprint 28 SP-vel zárul.

**Előfeltétel:** a Sprint 4 nyitott pontjai ide nem számítanak, de a FIN-407 és a FIN-403 csak utánuk kezdhető: a FIN-410 mérése, valamint a FIN-412 és a FIN-312 saját dokumentumos pontjai.

**Változás a tervhez képest:**

- **FIN-411:** a Sprint 7-be került, mert nincs még valódi visszaváltási bizonylat, és a formátumot nem szabad kitalálni. A beváltott utalvány enélkül is csökkenti a várható összeget.
- **FIN-406:** 5 helyett 8 SP. A tervezett blokk és tétel mellett a számlát, a döntéseket, a duplikátumokat és a kiszerelést is kezelnie kell.
- **FIN-501:** 3 helyett 5 SP. A Szabályok oldal, a bronz tárolás és a worker szinkronja is a része.
- **FIN-409:** 3 helyett 5 SP. A Betétdíj oldal, a bronz tárolás, a worker szinkronja és a riportkártya is a része.
- **FIN-206:** új jegy, a Metabase helyett Streamlit ([[0014-streamlit-a-metabase-helyett|ADR 0014]]).

**Adat:** a tesztadatok kitaláltak. A dbt egységtesztek és a seedek nem tartalmazhatnak valódi nevet vagy összeget, a szabályok ezért a bronzban élnek, nem a repóban.

## FIN-406 Silver tétel szint · 8 SP

**Story:** adatgazdaként a blokkokat és számlákat tételenként akarom látni a silverben, hogy a kiadás kategóriákra bomoljon, és a javításaim érvényesüljenek.

**Részfeladatok**

- [x] A `sources.yml` bővítése: `receipt_parse`, `review_decision`, a `raw_document` oszlopai 📅 2027-01-10
- [x] `silver.documents`: dokumentumonként a legutóbbi feldolgozás és döntés, a beszámítás a lenti táblázat szerint 📅 2027-01-10
- [x] Duplikátum: azonos adószám és sorszám esetén csak a legkorábbi dokumentum számít 📅 2027-01-10
- [x] `silver.receipt_items`: tételsorok a javított vagy a feldolgozott adatból, sorszámmal és típussal 📅 2027-01-10
- [x] A kedvezménysor a fölötte álló tétel kategóriáját kapja 📅 2027-01-10
- [x] Kiszerelés kinyerése a tételnévből: `3DB`, `175G`, `1,5L` 📅 2027-01-10
- [x] `silver.document_payments`: fizetési sorok, köztük a `deposit_voucher` 📅 2027-01-10
- [x] `silver.stores`: bolt adószám szerint, egy névvel 📅 2027-01-10
- [x] `silver.transactions` bővítése: dokumentumonként és kategóriánként egy kiadássor, a betétdíj és az utalvány nélkül 📅 2027-01-10
- [x] Tesztek: a tételek kiadják a végösszeget, nincs duplikált dokumentum, a betétdíj nincs a kiadások között 📅 2027-01-10
- [x] A `finance-dbt.timer` óránként fut, hogy a döntés egy órán belül a riportokban is látsszon 📅 2027-01-10

**Elfogadási feltételek**

- [x] Egy `ok` blokk tételei megjelennek a silverben, és a kiadása a `gold.category_month` táblában is
- [x] Javítás után a silver a javított értéket mutatja, a bronz változatlan
- [x] Az ellenőrzésre váró, a nem kiadás és az elvetett dokumentum nem számít a kiadásba
- [x] Újranyitás után az érvényes döntés megszűnik, és az új döntés számít
- [x] Ugyanaz a blokk két külön fotóról egyszer számít
- [x] A betétdíj és a beváltott utalvány nincs a kiadások között
- [x] Egy dokumentum kiadása, betétdíja és utalványa együtt legfeljebb 2 Ft-tal tér el a végösszegtől
- [x] A `3DB`, `175G` és `1,5L` kiszerelés külön mezőben van, a tételnév változatlan
- [x] `dbt build` hiba nélkül fut a valódi adatokon, és a kézi bejegyzések nem változnak
- [x] Saját dokumentum tartalma nem került a repóba

**Beszámítás:** ezt egyedül a `silver.documents` dönti el ([[0013-beszamitas-a-silverben|ADR 0013]]).

| Legutóbbi feldolgozás | Legutóbbi döntés | Számít? | Adat |
| --- | --- | --- | --- |
| `ok` | nincs vagy `reopened` | igen | feldolgozott |
| bármi, kivéve nem kiadás | `approved` | igen | feldolgozott |
| bármi | `corrected` | igen | javított |
| bármi | `rejected` | nem | – |
| `review`, `unparsed` | nincs vagy `reopened` | nem, függő | – |
| nem kiadás | nincs, `approved` vagy `reopened` | nem | – |

**Egyéb szabályok**

- **Dátum:** javított dátum, beolvasott dátum, beírt dátum, végül a feltöltés napja.
- **Kategória:** szabály, a dokumentum egyetlen címkéje, végül `besorolatlan`. A szabályt a FIN-501 adja, addig csak a másik kettő működik.
- **Pénznem:** a nem forintos számla csak forintra javítva számít, mert a silver csak forintot tart.

| Modell | Egy sora | Mire kell |
| --- | --- | --- |
| `documents` | Dokumentum | Beszámítás, bolt, dátum, végösszeg, vásárló, fizető fél |
| `receipt_items` | Tétel | Kategória, típus, mennyiség, kiszerelés, tételár-történet |
| `document_payments` | Fizetési sor | Betétdíj, később a kivonat párosítása |
| `stores` | Adószám | Egységes boltnév |
| `transactions` | Tranzakció | A meglévő gold modellek, változatlan oszlopokkal |

**Ami nem része:** a tételek besorolása kérdésekkel a FIN-502-é, a banki párosítás az E6-é.

## FIN-206 Streamlit riportfelület, a Metabase kivezetése · 8 SP

**Story:** felhasználóként egyszerű, magyar riportoldalakat akarok, hogy a számokat elemzőeszköz kezelése nélkül lássam.

**Részfeladatok**

- [x] `reports/` mappa: Dockerfile, rögzített függőségek, oldalak, tesztek 📅 2027-01-10
- [x] `reports` szolgáltatás a Compose-ban, `127.0.0.1:8501`, healthcheckkel 📅 2027-01-10
- [x] A `mb_reader` szerepkör `report_reader` néven marad, csak a goldot olvassa 📅 2027-01-10
- [x] Használati statisztika és külső címlekérdezés kikapcsolva 📅 2027-01-10
- [x] `gold.expense_documents` és `gold.expense_items`, hogy a Kiadások oldal is csak a goldot olvassa 📅 2027-01-10
- [x] Közös felső menü és magyar számformátum: szóközös ezres tagolás, Altair-diagramok 📅 2027-01-10
- [x] Áttekintés oldal: a mostani dashboard kártyái, ez a hónap az előzőhöz és az átlaghoz képest 📅 2027-01-10
- [x] Kiadások oldal: szűrés arra, ki fizetett, lefúrás a dokumentumtól a tételekig, onnan az Ellenőrzés képernyőre 📅 2027-01-10
- [x] Riportok menüpont a webappban, az állapotoldal kártyája a Metabase helyett a `reports` szolgáltatást nézi 📅 2027-01-10
- [x] A Metabase kivezetése: Compose-szolgáltatás, `scripts/metabase-*.sh`, `MB_*` és `METABASE_*` beállítások, mentés, visszaállítási próba, README 📅 2027-01-10
- [x] Egyszeri lépés mentés után: a `metabase` adatbázis és a `metabase_owner` szerepkör törlése 📅 2027-01-10
- [x] Oldaltesztek kitalált adattal, a Streamlit `AppTest` eszközével 📅 2027-01-10

**Elfogadási feltételek**

- [x] Az új Áttekintés ugyanazokat a számokat adja, mint a Metabase dashboardja, ezt a kivezetés előtt össze kell vetni
- [x] A Kiadások oldalon egy sor kiválasztása után látszanak a tételek, és a gomb az Ellenőrzés képernyőre visz
- [x] A szűrés arra, ki fizetett, a tételekre is érvényes
- [x] A `report_reader` nem olvassa a bronzot és a silvert, és nem tud írni
- [x] Indításkor és használat közben nem megy kérés külső szolgáltatáshoz, sem statisztika
- [x] Telefonméretben nincs vízszintes görgetés, és a menü elérhető
- [x] Az állapotoldal jelzi, ha a riportfelület leáll
- [x] A Metabase után a `scripts/backup.sh`, a `scripts/restore-test.sh` és a CI hibátlanul fut
- [x] Saját adat nem került a repóba

**Próba 2026-11-01-én:** egy eldobható, repón kívüli próba három oldalt épített meg. Működött a felső menü, a kiválasztható táblázatsor, a csúszkás what-if, a mondatos javaslat és a link az Ellenőrzés képernyőre. Használat közben kb. 140 MB memóriát foglalt, a futó Metabase kb. 1,5 GB-ot.

**A próba tanulságai**

- **Külső hívás:** a Streamlit alapból statisztikát küld, és induláskor külső szolgáltatástól kérdezi a nyilvános IP-címet. Mindkettőt ki kell kapcsolni, ezt elfogadási feltétel ellenőrzi.
- **Számformátum:** a beépített diagramok tengelye nem állítható magyarra, ezért Altair kell.
- **Főoldal:** az alapértelmezett oldal a `/` címen van, a saját útvonala „Page not found” ablakot ad.
- **Telefon:** a felső menü összecsukódik, és egy nyitógombbal érhető el. Keskeny böngészőablakban ellenőrizve, valódi telefonon még nem.

**Ami nem része:** a Közös háztartás és a Személyes fül a FIN-605-tel, a Célok és a what-if a FIN-703-mal készül, mert ezekhez hiányzik a gold adat, például a közös kassza. A külső elérés és a belépés külön döntés, amikor a riport helye eldől. A kinézet a FIN-207-ben készül, amikor már van elég valódi adat.

## FIN-501 Címke- és boltszabályok · 5 SP

**Story:** felhasználóként szabályokat akarok felvenni, hogy a visszatérő tételek és boltok maguktól a helyükre kerüljenek.

**Részfeladatok**

- [x] Migráció: `bronze.rule_event`, csak hozzáfűzhető 📅 2027-01-10
- [x] Postaláda: szabályok az SQLite-ban, worker API a lehúzáshoz és a nyugtázáshoz 📅 2027-01-10
- [x] Worker: a szabályesemények a bronzba kerülnek, az Ellenőrzés döntéseihez hasonlóan 📅 2027-01-10
- [x] Szabályok oldal a menüben: lista, új szabály, kikapcsolás 📅 2027-01-10
- [x] Tételszabály: ha a név tartalmazza a mintát, a tétel megkapja a kategóriát, ékezet nélkül egyeztetve 📅 2027-01-10
- [x] Boltszabály: adószámhoz egységes név 📅 2027-01-10
- [x] Több találatnál a hosszabb minta nyer, egyezésnél a régebbi szabály 📅 2027-01-10
- [x] A szabály a `silver.receipt_items` és a `silver.stores` modellben érvényesül, a régi blokkokra is 📅 2027-01-10
- [x] Kitalált adatú dbt egységtesztek 📅 2027-01-10

**Elfogadási feltételek**

- [x] Szabályra illeszkedő tétel automatikusan címkét kap, a régi blokkokon is
- [x] A szabály a blokkon rövidített, ékezet nélküli névre is illeszkedik
- [x] Két címkés blokknál a szabály nélküli tétel `besorolatlan` marad
- [x] A boltszabály után a riportok egy néven mutatják a boltot
- [x] Kikapcsolt szabály a következő dbt-futás után nem érvényesül, a bronzban megmarad
- [x] Ismeretlen kategória nem menthető
- [x] Leállított workernél a szabály a webappban vár, és újraindítás után a bronzba kerül
- [x] A repóban nincs valódi szabály

```sql
create table bronze.rule_event (
  id           uuid primary key,
  rule_id      uuid not null,
  rule_type    text not null check (rule_type in ('category', 'store')),
  pattern      text not null,
  target_value text not null,
  active       boolean not null,
  created_by   text not null,
  created_at   timestamptz not null,
  ingested_at  timestamptz not null default now()
);
```

A bronz csak bővül, ezért a kikapcsolás új sor ugyanazzal a `rule_id` értékkel. Szabályonként a legutóbbi sor érvényes. A tételről közvetlen szabálykészítés a FIN-502-höz tartozik.

## FIN-409 DRS-betétdíj külön vezetése · 5 SP

**Story:** a háztartás tagjaként látni akarom, mennyi betétdíj vár visszaváltásra, hogy ez a pénz ne kiadásként jelenjen meg, és tudjam nullázni.

**Részfeladatok**

- [x] Migráció: `bronze.deposit_correction`, csak hozzáfűzhető 📅 2027-01-10
- [x] Postaláda és worker API: a kézi állítás és a nullázás a szabályokhoz hasonlóan jut a bronzba 📅 2027-01-10
- [x] `silver.deposit_movements`: mozgások a lenti táblázat szerint 📅 2027-01-10
- [x] `gold.expected_deposit`: a várható összeg, naponta visszamenőleg is 📅 2027-01-10
- [x] Betétdíj oldal a menüben: várható összeg, állítás, nullázás, legutóbbi mozgások 📅 2027-01-10
- [x] A worker körönként visszatölti az egyenleget a webappnak, mert az a goldot nem éri el 📅 2027-01-10
- [x] Várható betétdíj kártya az Áttekintés riporton 📅 2027-01-10
- [x] Kitalált adatú dbt egységtesztek 📅 2027-01-10

**Elfogadási feltételek**

- [x] A blokkon fizetett betétdíj nincs a kiadások között, és növeli a várható összeget
- [x] A beváltott DRS-utalvány csökkenti a várható összeget, a kiadást nem
- [x] Két utalvány egy blokkon mindkét összeggel csökkent
- [x] A várható összeg kézzel állítható, nullázás után 0, és a később fizetett betétdíj újra növeli
- [x] A nullázás akkor is pontos, ha a dbt csak utána fut le
- [x] A bronz nem változik, a kézi műveletek külön sorként maradnak meg
- [x] Az egyenleg a Betétdíj oldalon és a riportban is látszik, az oldalon a frissítés idejével

| Mozgás | Hatás | Forrás |
| --- | --- | --- |
| Blokkon fizetett betétdíj | Növeli | `kind = deposit` tétel |
| Beváltott DRS-utalvány | Csökkenti | `deposit_voucher` fizetési sor, vagy `kind = voucher` tétel |
| Kézi állítás | Növeli vagy csökkenti | `bronze.deposit_correction`, `adjust` |
| Nullázás | Az akkori egyenleget vonja le | `bronze.deposit_correction`, `reset` |

**Negatív egyenleg:** a régebbi vásárlások betétdíja nincs a rendszerben, ezért egy beváltott utalvány negatívba viheti az összeget. A negatív érték nem hiba, de az oldal jelzi. Induláskor és a FIN-309 után egy kézi állítás adja a nyitó egyenleget.

**Visszaváltási bizonylat:** a FIN-411-gyel a Sprint 7-ben jön. A párosításnál a már beváltott utalványt nem szabad másodszor levonni.

```sql
create table bronze.deposit_correction (
  id          uuid primary key,
  kind        text not null check (kind in ('adjust', 'reset')),
  amount      numeric(12, 2),
  created_by  text not null,
  created_at  timestamptz not null,
  ingested_at timestamptz not null default now()
);
```

## FIN-407 Mérés 20–30 saját blokkon · 2 SP

**Story:** adatgazdaként nagyobb mintán akarom mérni a beolvasást, hogy eldőljön, kell-e finomhangolt modell.

**Részfeladatok**

- [ ] 20–30 saját blokk feltöltése, több boltból, kártyás és készpénzes is 📅 2027-01-10
- [ ] Az Ellenőrzés képernyőn az eredeti összevetése a feldolgozott adattal 📅 2027-01-10
- [ ] Eredmény a lenti táblázatban, csak arányokkal 📅 2027-01-10
- [ ] A hiányzó sorminták felvétele, kitalált tesztblokkal 📅 2027-01-10
- [ ] Döntés a FIN-801–804-ről 📅 2027-01-10

**Elfogadási feltételek**

- [ ] A mérés legalább 20 saját blokkon készült el, a netes minták nélkül
- [ ] Mezőnként le van írva a pontosság
- [ ] Le van írva, hány blokk lett `ok`, `review` és `unparsed`, és a `review` okai
- [ ] Le van írva a `besorolatlan` tételek aránya
- [ ] Minden `ok` blokk végösszege egyezik a papírblokkal
- [ ] A FIN-801–804-ről döntés született
- [ ] Saját blokk szövege, boltja vagy összege nem került a repóba

**A döntés szabálya:** a finomhangolás akkor kell, ha a számjegyek olvasási hibája miatt a blokkok legalább 10%-a `review` lesz. Ha a hibák többsége sorminta, a szabályokat kell bővíteni, nem a modellt. Ezt a határt a mérés előtt rögzítjük, hogy az eredmény ne befolyásolja.

| Mező | Pontosság |
| --- | --- |
| Tételszám | mérendő |
| Tétel értéke | mérendő |
| Végösszeg | mérendő |
| Dátum | mérendő |
| Adószám | mérendő |

## FIN-403 PaddleOCR második olvasat · 3 SP

**Feltétel:** csak akkor indul, ha a FIN-410 szerint a kiolvasási hiba miatti `review` blokkok aránya 20% fölött van. Az eddigi dokumentumokon ilyen hibát nem láttunk, ezért várhatóan kimarad.

**Story:** adatgazdaként a bizonytalan blokkot második olvasattal akarom ellenőrizni, hogy kevesebb kérdés jusson hozzám.

**Részfeladatok**

- [ ] PaddleOCR a workerben, magyar modellel 📅 2027-01-10
- [ ] Második olvasat csak `review` és `unparsed` blokkra 📅 2027-01-10
- [ ] Az olvasat saját sorként a `bronze.extraction` táblába kerül 📅 2027-01-10

**Elfogadási feltételek**

- [ ] Bizonytalan blokknál az OCR-szöveg is a bronzba kerül
- [ ] Az `ok` blokk nem kap második olvasatot
- [ ] Le van mérve, hány `review` blokkot old meg a második olvasat

## Események és nyitott kérdések

- [ ] Sprinttervezés, kb. 30 perc 📅 2026-12-28
- [ ] Heti áttekintés, kb. 15 perc 📅 2027-01-04
- [ ] Demó és retró, kb. 30 perc 📅 2027-01-10
- [ ] Kiadás: `v0.5.0` a [[Release folyamat]] szerint 📅 2027-01-10

**Eldöntve a tervezés előtt**

- [x] A kiadásba csak a rendben lévő, jóváhagyott vagy javított dokumentum számít ([[0013-beszamitas-a-silverben|ADR 0013]]).
- [x] A szabály nélküli tétel több címkés blokknál `besorolatlan` marad a FIN-502-ig.
- [x] A szabályok külön Szabályok oldalon jönnek létre. A tételről közvetlen szabálykészítés a Sprint 7-be tartozik.
- [x] A FIN-411 a Sprint 7-be kerül, amíg nincs valódi visszaváltási bizonylat.
- [x] A `bronze.review_decision` a korrekciós tábla, külön tábla nem készül.
- [x] A dbt óránként fut, mert a konténerben futó worker nem tud dbt-t indítani.
- [x] A riportok Streamlitben készülnek, a Metabase kikerül, és nem marad mellette szabad elemzésre ([[0014-streamlit-a-metabase-helyett|ADR 0014]]).
- [x] A riportfelület az otthoni stackben fut a gold mellett, ezért a Pi-ről nem kell elérnie a goldot.
