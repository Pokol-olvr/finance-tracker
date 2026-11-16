# 0015 Termékcsaládok és egységár a silverben

**Állapot:** elfogadva

**Dátum:** 2026-11-16

## Kontextus

A kategória egy szintű, ezért egy 18 450 Ft-os vásárlásból csak az látszik, mennyi volt élelmiszer. A „CSIPERKE 250G”, az „XXL CSIPERKE” és a „SB BARNA CSIPERKE 500” három külön tétel, pedig ugyanaz a termék, és jórészt csak a kiszerelés különbözik. Így nem követhető, hogyan drágul nálunk egy termék, ami az [[Üzleti koncepció]] személyes infláció pontja.

A saját blokkokon három kiszerelési forma fordul elő: a mérlegelt tétel (`0,618 KG × 699 Ft/KG`), a névben álló kiszerelés (`175G`, `ACTIVIA MEGGY 4X120G`) és a kiszerelés nélküli név (`XXL CSIPERKE`, `SB BARNA CSIPERKE 500`). Egyes boltok a cikkszámot (EAN) is kiírják a tétel fölé.

## Döntés

A tétel három szinten sorolódik be: kategória, termékcsalád, termék, például `élelmiszer/gomba/csiperke`. A kiszerelés nem szint, hanem a tétel adata, ezért a csiperke ára dobozmérettől függetlenül összevethető.

- **Termékszabály:** a meglévő szabálytáblában új `product` típus. A minta a név részlete vagy az EAN, a cél a teljes út. A termékből jön a kategória, és a termékszabály erősebb a kategóriaszabálynál.
- **Sorrend:** több találatnál az EAN nyer, utána a hosszabb minta, egyezésnél a régebbi szabály.
- **Kiszerelésszabály:** új `pack` típus a kiszerelés nélküli nevekhez, például `SB BARNA CSIPERKE 500` → `500G`.
- **Egységár:** a silver alapegységben számol: Ft/kg, Ft/l vagy Ft/db. A mérlegelt tételnél a mért mennyiség az alap, különben darabszám × csomagszám × kiszerelés. Az alatta álló kedvezmény csökkenti az egységárat.
- **EAN:** a blokkfeldolgozó a `Cikkszám:` sort a következő tételhez rendeli, és a javítás is megőrzi.
- **Árnapló:** a `gold.product_prices` termékenként, boltonként és hónaponként a súlyozott egységárat adja.

A szabályok a bronzban élnek, ezért visszamenőleg minden dokumentumra érvényesek. A blokkokat nem kell újra feltölteni: a `PARSER_VERSION` emelése után a worker modell nélkül újra feldolgozza a tárolt szövegeket, a dbt pedig újraépíti a silvert.

## Elvetett alternatívák

- **Tetszőleges mélységű fa:** rugalmasabb, de a riportokban nehezebb összesíteni, és a háztartás méretéhez három szint elég.
- **Külön terméktábla saját oldallal:** tisztább adatmodell, de új bronz tábla, kimenő esemény és worker-szinkron kellene hozzá. A szabálytábla ezt már tudja, és a termék útja maga a termék.
- **Kiszerelés a blokkfeldolgozóban:** a javított tételnevekre nem érvényesülne, a dbt viszont a javított nevet is olvassa.
- **Automatikus termékfelismerés:** a FIN-503 szövegosztályozója később termékre tippelhet, ehhez viszont előbb kézi szabályokkal felcímkézett tételek kellenek.

## Következmények

- A termékszabályt kézzel kell felvenni. A tételről közvetlen szabálykészítés a Sprint 7-ben jön.
- A kiszerelés nélküli, nem mérlegelt tétel egységára Ft/db, amíg nincs hozzá kiszerelésszabály.
- A kategória- és a termékszabály egymás mellett él: a régi kategóriaszabályok érvényesek maradnak, amíg a tételre nincs termékszabály.
- A riportokban az árnapló nézete még nem készült el, a gold tábla már lekérdezhető.
