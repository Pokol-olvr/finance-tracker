---
projekt: Pénzügyi nyomkövető
sprint: S4
kezdes: 2026-12-14
vege: 2026-12-27
story_pont: 12
tags: [penzugy, sprint]
---

# Sprint 4

Vissza: [[Fejlesztési terv]]

## Sprint cél

**Egy feltöltött blokk szöveges olvasatából pontos tételek, végösszeg és fizetési adatok lesznek, a hibás blokk pedig ellenőrzésre jelölve látszik.** A sprint 2026-12-14 és 2026-12-27 között tart, 12 story ponttal.

| Kulcs | Jegy | SP | Függ tőle |
| --- | --- | --- | --- |
| FIN-402 | Blokkfeldolgozó a szöveges olvasatra | 5 | FIN-408 |
| FIN-404 | Automatikus ellenőrzés | 5 | FIN-402 |
| FIN-410 | Mérés 5–10 saját blokkon | 2 | FIN-402, FIN-404 |

Javasolt sorrend: FIN-402, FIN-404, végül a FIN-410. A saját blokkokat érdemes már a sprint elején feltölteni, mert a szabályok ezek szöveges olvasatából pontosíthatók.

**Irányváltás:** a Sprint 3 után egy saját blokkon a JSON-olvasat összekeverte a neveket és az árakat, a szöveges olvasatban viszont minden szám helyes volt. Ezért a szerkezetet saját, szabályalapú feldolgozó adja, a JSON-olvasat kikerül ([[0009-szabalyalapu-blokkfeldolgozo|ADR 0009]]). A FIN-403 feltételes lett, és az 5. sprintbe került.

**Adat:** a tesztek blokkjai kitaláltak, a `worker/tests/receipts/` mappában, szöveges fájlként. Saját blokk szövege nem kerülhet a repóba, ide csak arányok és kitalált példák jönnek.

## FIN-402 Blokkfeldolgozó a szöveges olvasatra · 5 SP

**Story:** felhasználóként azt akarom, hogy a blokk tételei és összegei pontosak legyenek, hogy a modell párosítási hibái ne kerüljenek az adataim közé.

**Részfeladatok**

- [ ] `worker/app/receipt_parser.py`: tiszta függvény, a szöveges olvasatból szerkezetet ad, hálózat és adatbázis nélkül 📅 2026-12-27
- [ ] A lenti sormintákra épülő szabályok, `PARSER_VERSION` verzióval 📅 2026-12-27
- [ ] Összegek egész forintban; a szóközös ezres tagolás egyben marad 📅 2026-12-27
- [ ] Minden tétel megőrzi a nyers nevet, mellette ékezet nélküli egyeztető kulcsot kap (`match_name`) 📅 2026-12-27
- [ ] A DRS-sor `kind = deposit`, a beváltott utalvány `kind = voucher` jelölést kap a FIN-409-hez és a FIN-411-hez 📅 2026-12-27
- [ ] `bronze.receipt_parse` tábla migrációval, csak hozzáfűzhetően 📅 2026-12-27
- [ ] A worker a kiolvasás után futtatja a feldolgozót 📅 2026-12-27
- [ ] Új `PARSER_VERSION` esetén a worker a meglévő szövegeket is újra feldolgozza, modellfutás nélkül 📅 2026-12-27
- [ ] A JSON-olvasat kivezetése: egy modellhívás marad, a `PROMPT_VERSION` 2 lesz; a régi sorok a bronzban maradnak 📅 2026-12-27
- [ ] `scripts/last-extraction.sh`: a feldolgozott tételek és az ellenőrzések is látszanak 📅 2026-12-27
- [ ] pytest-tesztek kitalált blokkokkal, mintánként a várt eredménnyel 📅 2026-12-27
- [ ] Migrációs teszt: a `scripts/test-bronze.sh` az új táblára is ellenőrzi a hozzáfűzés-védelmet 📅 2026-12-27
- [ ] README: a feldolgozó működése és új formátum felvétele 📅 2026-12-27

**Elfogadási feltételek**

- [ ] A lenti kitalált blokkból 2 tétel és 1 betétdíj lesz, a pontos értékekkel
- [ ] A `1 346` összeg 1346 Ft, és egyetlen ezres tagolású összeg sem veszíti el az elejét
- [ ] Név végén álló mennyiség (`1,5L`, `500G`) nem lesz ár
- [ ] A kétsoros tételnél a név az első, az érték a második sorból jön
- [ ] A hibás ékezetű név (`GÒNGYÓLEG`) is betétdíjnak számít
- [ ] Új `PARSER_VERSION` után a meglévő szövegből új `bronze.receipt_parse` sor lesz, modellhívás nélkül
- [ ] Ugyanarra a kiolvasásra ugyanazzal a verzióval nem készül második sor
- [ ] Egy blokk feldolgozása a modell nélkül 1 másodperc alatt lefut
- [ ] A feldolgozó hibája nem állítja meg a workert, a blokk `unparsed` állapotba kerül

**Kitalált minta**

```text
TESZT ÉLELMISZER KFT
1111 Budapest, Próba utca 1.
ADOSZAM: 12345678-2-41

AFA Megnevezés
Menny. Me. Egységár Érték

C00 ÁSVÁNYVÍZ 1,5L
3 DB * 199 Ft/DB 597
E00 DRS GÖNGYÖLEG
3 DB * 50 Ft/DB 150
B00 KENYÉR 500G 599

ÖSSZESEN: 1 346 Ft

KESZPENZ: 2 000 Ft
VISSZAJARO: 655 Ft

NYUGTASZAM:
2026.12.14. 0042/00017
17:42
```

Várt eredmény: 1196 Ft kiadás, 150 Ft betétdíj, 1346 Ft végösszeg. A készpénz 1345 Ft-ra kerekít.

**Sorminták**

| Sor | Minta | Mit ad |
| --- | --- | --- |
| Tétel kezdete | `C00 ÁSVÁNYVÍZ 1,5L` | ÁFA-kód, név |
| Egysoros tétel | `B00 KENYÉR 500G 599` | ÁFA-kód, név, érték |
| Mennyiségsor | `3 DB * 199 Ft/DB 597` | Mennyiség, egység, egységár, érték |
| Mért tétel | `0,532 KG * 1 299 Ft/KG 691` | Tört mennyiség, egységár, érték |
| Betétdíj | `E00 DRS GÖNGYÖLEG` | Mint a tétel, `kind = deposit` |
| Kedvezmény | `KEDVEZMÉNY -120` | Negatív érték, `kind = discount` |
| Utalvány | `DRS UTALVÁNY -300` | Negatív érték, `kind = voucher`; nem csökkenti a kiadást |
| Végösszeg | `ÖSSZESEN: 1 346 Ft` | Végösszeg |
| Fizetés | `KESZPENZ:`, `BANKKARTYA:`, `VISSZAJARO:` | Fizetési mód, fizetett összeg, visszajáró |
| Adószám | `ADOSZAM: 12345678-2-41` | A bolt azonosítója |
| Nyugtaszám | `NYUGTASZAM:`, utána dátum és szám | Dátum, idő, nyugtaszám |

Az egysoros, a kétsoros tétel és a végösszeg formája egyetlen saját blokkon igazolt. A mért tétel, a kedvezmény, az utalvány és a kerekítés sora feltételezés, ezeket a FIN-410 saját blokkjain ellenőrizni kell. Az ÁFA-kódot szövegként tároljuk, a jelentésére nem építünk, mert a forrását nem találtuk meg.

**Tábla: `bronze.receipt_parse`**

| Mező | Megjegyzés |
| --- | --- |
| `id` | UUID |
| `extraction_id` | A `bronze.extraction` sora |
| `parser_version` | A feldolgozó verziója |
| `status` | `ok`, `review` vagy `unparsed` |
| `payload` | A feldolgozott blokk JSON-ként |
| `checks` | Az ellenőrzések eredménye JSON-ként, a FIN-404 tölti |
| `created_at` | Létrehozás ideje |

Az `extraction_id` és a `parser_version` együtt egyedi. A nyers szöveg a `bronze.extraction` táblában marad, ezért a feldolgozó bármikor újrafuttatható.

## FIN-404 Automatikus ellenőrzés · 5 SP

**Story:** felhasználóként azt akarom, hogy csak a bizonytalan blokkokkal kelljen foglalkoznom, hogy a rendszer ne kérdezzen feleslegesen, és rossz adat se csússzon át.

**Részfeladatok**

- [ ] A lenti ellenőrzések a feldolgozott blokkon, eredményük a `checks` mezőbe kerül 📅 2026-12-27
- [ ] Állapot: `ok`, ha minden ellenőrzés sikeres; `review`, ha valamelyik nem; `unparsed`, ha nincs tétel vagy végösszeg 📅 2026-12-27
- [ ] Az állapotoldal „rendben” felirata csak `ok` blokkra jelenik meg, a többi „ellenőrzés kell” vagy „nem feldolgozható” 📅 2026-12-27
- [ ] A Feltöltés kártyán „Ellenőrzésre vár” szám 📅 2026-12-27
- [ ] pytest-tesztek ellenőrzésenként, sikeres és hibás kitalált blokkal 📅 2026-12-27

**Elfogadási feltételek**

- [ ] A kitalált minta `ok` állapotú, a kerekítés ellenére
- [ ] Egy tétel átírt áráról az összegellenőrzés `review` állapotot ad
- [ ] Eltérő beírt és beolvasott dátum `review` állapotot ad
- [ ] Ugyanaz a blokk újrafotózva, eltérő hash-sel `review` állapotot ad, és nem számít kétszer
- [ ] Bankkártyás blokknál nincs kerekítési tűrés
- [ ] Az állapotoldalon a „rendben” felirat érvényes JSON-ra már nem jelenik meg, csak sikeres ellenőrzésre
- [ ] A `review` blokk nyers képe és szövege a Garage-ban és a bronzban megmarad

**Ellenőrzések**

| Név | Szabály | Mikor nem fut |
| --- | --- | --- |
| `sum` | Tételek + betétdíj + kedvezmény + utalvány = végösszeg | Soha |
| `line_total` | Mennyiség × egységár = érték, 1 Ft tűréssel | Egysoros tételnél |
| `payment` | Fizetett − visszajáró = végösszeg; készpénznél legfeljebb 2 Ft eltérés | Ha nincs fizetett összeg a blokkon |
| `date` | A beolvasott dátum = a feltöltéskor beírt dátum | Ha nincs beolvasott dátum |
| `duplicate` | Az adószám és a nyugtaszám egy másik dokumentumnál nem szerepel | Ha valamelyik hiányzik |

A készpénzes kerekítés a végösszeget 0-ra vagy 5-re végződőre viszi, ezért legfeljebb 2 Ft az eltérés; bankkártyánál alapból nincs kerekítés ([forrás](https://njt.jog.gov.hu/jogszabaly/2008-3-00-00)). A betétdíj az ellenőrzésben benne van, mert a végösszeg tartalmazza.

Az ellenőrzési sor képernyője a FIN-405 feladata. Addig a `review` blokkok a `scripts/last-extraction.sh` paranccsal nézhetők meg.

## FIN-410 Mérés 5–10 saját blokkon · 2 SP

**Story:** adatgazdaként saját blokkokon akarom mérni a feldolgozót, hogy lássam, elég-e a szöveges olvasat, vagy kell a második olvasat.

**Részfeladatok**

- [ ] Legalább 5 saját blokk feltöltése, legalább 3 boltból, köztük kártyás és készpénzes 📅 2026-12-27
- [ ] A hiányzó sorminták felvétele; hozzájuk kitalált tesztblokk 📅 2026-12-27
- [ ] Eredmény a lenti táblázatban, csak arányokkal 📅 2026-12-27
- [ ] Döntés a FIN-403-ról és a kép méretéről 📅 2026-12-27

**Elfogadási feltételek**

- [ ] A mérés legalább 5 blokkon, legalább 3 boltból elkészült
- [ ] Mezőnként le van írva a pontosság: tételszám, érték, végösszeg, dátum, adószám
- [ ] Le van írva, hány blokk lett `ok`, `review` és `unparsed`
- [ ] Minden `ok` blokk végösszege egyezik a papírblokkal
- [ ] Saját blokk szövege, boltja vagy összege nem került a repóba

**A döntés szabálya**

- **FIN-403:** akkor kell, ha a kiolvasási hiba miatt `review` blokkok aránya 20% fölött van; különben kimarad.
- **Képméret:** ha egy blokk számjegye hibás a szöveges olvasatban, ugyanazt a fotót 2000 pixelen is meg kell mérni.

| Mező | Pontosság |
| --- | --- |
| Tételszám | mérendő |
| Tétel értéke | mérendő |
| Végösszeg | mérendő |
| Dátum | mérendő |
| Adószám | mérendő |

## Események és nyitott kérdések

- [ ] Sprinttervezés, kb. 30 perc 📅 2026-12-14
- [ ] Heti áttekintés, kb. 15 perc 📅 2026-12-21
- [ ] Demó és retró, kb. 30 perc 📅 2026-12-27
- [ ] Kiadás: `v0.4.0` a [[Release folyamat]] szerint 📅 2026-12-27

**Eldöntve a tervezés előtt**

- [x] A szerkezet a szöveges olvasatból jön, a JSON-olvasat kikerül ([[0009-szabalyalapu-blokkfeldolgozo|ADR 0009]]).
- [x] Az ékezeteket nem írjuk vissza: az egyeztetés ékezet nélkül történik, a nyers szöveg megmarad.
- [x] A bolt azonosítója az adószám, nem a név. A boltok egységesítése a FIN-406 feladata.
- [x] A DRS-betétdíj nem kiadás ([[Üzleti koncepció]]). A feldolgozó csak jelöli, a vezetését a FIN-409 végzi.
- [x] A visszaváltás bizonylata feltölthető, a FIN-411-gyel, az 5. sprintben. Ebben a sprintben a feldolgozó csak az utalványsort ismeri fel, és nem csökkenti vele a kiadást.
