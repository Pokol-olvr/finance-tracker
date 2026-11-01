# Dokumentációs útmutató

Ez a fájl a `docs/` mappa dokumentumainak írását és módosítását szabályozza. A mérce a meglévő négy dokumentum: ha egy eset nincs itt leírva, a hozzá legközelebb álló dokumentum mintáját kövesd. Ez a fájl nem projektdokumentum, ezért nincs frontmatterje, és nem hivatkozunk rá a többiből.

A projekt egy kétszemélyes háztartási pénzügyi nyomkövető, medallion adatrétegekkel és helyi blokkbeolvasással. A szoftvert egy ember fejleszti, a rendszert ketten használják.

## Dokumentumok és felelősségük

Minden állítás egy helyen él, a többi csak hivatkozik rá.

| Dokumentum | Kérdés, amire válaszol | Ami nem ide való |
| --- | --- | --- |
| [[Üzleti koncepció]] | Mit és miért? Üzleti döntések, BI-fülek, kockázatok | Eszközök, táblanevek, határidők |
| [[Technikai terv]] | Hogyan? Architektúra, eszközök, rétegek, költözés | Story-k, ütemezés részletei |
| [[Fejlesztési terv]] | Mikor és milyen sorrendben? Epicek, story-k, sprintek, munkaszabályok | Részfeladatok, megvalósítási minták |
| `Sprint N.md` | Pontosan mit csinálunk ebben a sprintben? | Új üzleti vagy technikai döntés |
| `adr/NNNN-cim.md` | Miért ezt választottuk, és mi volt az alternatíva? | Általános leírás |
| [[Release folyamat]] | Hogyan adunk ki és telepítünk? Verziózás, kiadási lépések, visszaállás | Az egyes kiadások tartalma |
| [[Változásnapló]] | Mi változott kiadásonként? | Tervek, indoklások |

Ütközésnél az üzleti kérdésben az Üzleti koncepció, a technikaiban a Technikai terv az irányadó. Ütközést ne javíts csendben: ha nem egyértelmű, melyik a helyes, kérdezz rá.

## Munkamenet

1. Olvasd el a módosítandó dokumentumot és mindazt, amire hat (lásd a táblázatot lent). Ne emlékezetből dolgozz.
2. Csak azt módosítsd, amit a feladat kér. A meglévő szöveget ne fogalmazd át és ne formázd újra mellékesen.
3. Az „Eldöntve” pontokat ne nyisd újra. Ha egy feladat ellentmond nekik, jelezd, mielőtt írnál.
4. Vezesd végig a változást a kapcsolódó dokumentumokon.
5. Futtasd le a lenti ellenőrzőlistát, és a válaszodban nevezd meg, mit módosítottál, és mi maradt nyitva.

| Ha ez változik | Ezt is frissítsd |
| --- | --- |
| Üzleti döntés | Üzleti koncepció „Döntések és nyitott kérdések”, érintett technikai rész, érintett story-k |
| Eszköz vagy architektúra | Technikai terv szövege, mermaid ábrája, Compose-táblázata és „Források” része; új döntésnél ADR |
| Story címe, pontja vagy epicje | Fejlesztési terv story-sora és epic-fejléce, a teljes SP a bevezetőben, az érintett sprintdokumentum |
| Sprint dátuma | Sprint-táblázat, Gantt-ábra, a 📅 dátumok, a sprintdokumentum frontmattere és bevezetője |
| Sprint story-listája | A sprintdokumentum `story_pont` mezője, cél-mondata, táblázata és javasolt sorrendje |
| A szoftver működése, telepítése vagy biztonsága | [[Változásnapló]] `## Kiadatlan` része |

## Dokumentumszerkezet

### Fájlok

- A fájlnév magyar, ékezetes, szóközzel, mint a címe: `Technikai terv.md`, `Sprint 2.md`.
- ADR: `adr/NNNN-kebab-cim.md`. A `0001-adr-sablon.md` a sablon, amelyet a FIN-101 hoz létre; a számozás folytatólagos, és ADR-t nem írunk át, hanem újabbal váltunk le.
- A DoD szerint ha a működés változik, a README vagy egy ADR is frissül.

### Frontmatter

Az értékek típusonként a meglévő mintát követik, a kulcsok ékezet nélküliek.

```yaml
---
projekt: Pénzügyi nyomkövető
tipus: technikai terv
datum: 2026-10-27
tags: [penzugy, projekt, architektura]
---
```

- A `datum` az utolsó érdemi módosítás napja.
- A Fejlesztési terv `datum` helyett `kezdes` és `vege` mezőt használ.
- A sprintdokumentum frontmattere: `projekt`, `sprint`, `kezdes`, `vege`, `story_pont`, `tags: [penzugy, sprint]`.

### Eleje

- Egyetlen H1, amely után közvetlenül a hivatkozássor jön.
- Tervdokumentumban: `Kapcsolódó: [[Üzleti koncepció]] · [[Fejlesztési terv]] · [[Sprint 1]]`
- Sprintdokumentumban: `Vissza: [[Fejlesztési terv]]`
- Dokumentumok között mindig `[[wikilink]]`; külső forrásra mindig Markdown-link.

### Fejlesztési terv

Epic-fejléc: `## FIN-E1 Név (S1, 12 SP)`, alatta egy „Kész, ha: …” mondat. A story sora Obsidian Tasks-formátumú, az elfogadás négy szóközzel behúzva:

```text
- [ ] FIN-101 Rövid cím · 2 SP #E1 #sprint/S1 📅 2026-11-15
    - Elfogadás: egy konkrét, ellenőrizhető eredmény
```

- A kulcs első számjegye az epic száma, a 📅 a sprint utolsó napja.
- A story pont Fibonacci-szám (1, 2, 3, 5, 8); ami 8 fölé menne, azt bontani kell.

### Sprintdokumentum

Sorrend: `## Sprint cél` (félkövér cél-mondat, időszak, SP), jegytáblázat `Kulcs | Jegy | SP | Függ tőle` oszlopokkal, javasolt sorrend, majd jegyenként egy szakasz, végül `## Események és nyitott kérdések`.

```text
## FIN-101 Cím · 2 SP

**Story:** szerepként akarok valamit, hogy elérjek valamit.

**Részfeladatok**

- [ ] Konkrét, egy ülésben elvégezhető lépés 📅 2026-11-15

**Elfogadási feltételek**

- [ ] Paranccsal vagy próbával ellenőrizhető eredmény
```

- A részfeladat dátuma a sprint vége; eseménynél és a tervezésen eldöntendő kérdésnél a saját napja.
- Elfogadási feltétel csak olyan lehet, ami igaz vagy hamis; a „jól működik” nem elég.
- Szakasz végén szerepelhet minta (SQL, mappaszerkezet, szerepkörtábla), ha a megvalósításhoz kell. A jegy kulcsa, címe és SP-je egyezzen a Fejlesztési tervvel; a cím lehet rövidebb.

### Változásnapló

A `## Kiadatlan` és a `## v0.1.0 · 2026-11-15` címsorokat a `scripts/release.sh` olvassa és írja, ezért a formájuk nem változhat. A bejegyzések szabályai: [[Release folyamat]].

### ADR

Amíg a sablon nem létezik, a szerkezet: Állapot, Kontextus, Döntés, Elvetett alternatívák, Következmények.

## Stílus

- Magyarul írj, tömören, rövid, kijelentő mondatokban. Egy gondolat egy mondat; felvezetés és összegző zárás nélkül.
- Minden állításnak legyen következménye vagy oka. Az érveket a konkrét helyzetből hozd („a 8B-s modell kb. 6 GB, így nem fér el a 1660 Ti-n”), ne általánosságból.
- Ajánlásnál mondd ki az ajánlást és az okát, az elvetett lehetőségnél pedig azt, hogy miért nem.
- Listaelem elején félkövér kulcsszó és kettőspont, ha a lista felsorolt fogalmakból áll: `- **Tailscale:** …`.
- Összehasonlításhoz táblázat, sorrendhez számozott lista, folyamathoz mermaid `flowchart`, ütemezéshez `gantt`. Ábrát csak akkor rajzolj, ha többet mond a szövegnél.
- Kódelem, fájl, parancs, tábla és környezeti változó backtickben: `dbt build`, `raw_document`, `MB_DB_HOST`.
- Magyar tipográfia: „idézőjel”, nagykötőjel tartományban (`S1–S2`, `20–30`) és címben (`Bronz – minden…`), szóközös ezres tagolás és `Ft` (`18 450 Ft`), elválasztónak `·`.
- A szakaszcímek mondatkezdő nagybetűsek és magyarok, a dátumok ISO-formátumúak (`2026-11-15`).
- Idegen szó magyar toldalékkal, kötőjellel, ahol kell: `Compose-fájl`, `Metabase-ben`, `Garage-dzsal`.

## Szóhasználat

Egy fogalomra mindig ugyanazt a szót használd.

| Szó | Jelentés |
| --- | --- |
| bronz, silver, gold | A rétegek szövegben; kódban a sémanevek: `bronze`, `silver`, `gold` |
| blokk | Bolti nyugta fotója vagy adata; a „számla” az A4-es, PDF-es vagy e-mailes számla |
| tétel | A blokk egy sora |
| címke | Feltöltéskor a blokkhoz adott jelölés; több is lehet, és a blokkra vonatkozik, nem a tételre |
| kategória | A tételhez rendelt besorolás a silverben |
| feltöltő | Aki rögzítette (`uploaded_by`) |
| fizető fél | A közös kártya vagy valamelyikünk (`payer`) |
| vásárló | Aki vásárolt, mindig személy (`purchased_by`); a fizető féllel ne cseréld fel |
| átvezetés | Saját zsebek közötti pénzmozgás; soha nem kiadás |
| betétdíj | A blokkon fizetett DRS-összeg, amely visszaváltáskor visszajár; soha nem kiadás |
| közös kártya | A mindennapi közös kiadások kártyája, 50/50 befizetéssel |
| Revolut-zseb | A közös célok pénze, külön a közös kártyától |
| szabad keret | Ami a fix és szokásos kiadások után átlagosan megmarad havonta |
| postaláda | A Pi szerepe: átmeneti tárolás, nem végleges adat |
| ellenőrzési sor, Ellenőrzés képernyő | A kivételek jóváhagyása; csak eltérésnél kérdezünk |
| laptop, főgép, Pi, Proxmox | A négy gép neve: a laptopon fut most a stack, a főgépen a tanítás; „otthoni stack” a Compose-ban futó feldolgozás |

## Tények és források

- A külső tényt (licenc, verzió, projektállapot, hardverigény, mért eredmény) a dokumentum írásakor ellenőrizd, és jelöld a forrását: `([forrás](url))`. A Technikai tervben a forrás a „Források” részbe is kerüljön.
- Ami időben változhat, annak legyen dátuma („2026 júniusa óta még alfa”).
- Becslést, mérést és ajánlást ne írj tényként. Ami még mérendő, arról mondd ki („ezt mérni kell”).
- Nem ellenőrzött tényt ne hagyj a szövegben jelölés nélkül.
- Rögzített értékeket (SP, dátum, tábla- és szerepkörnevek, verziók) a meglévő dokumentumokból vegyél, ne találj ki újat.
- A repó nyilvános. A dokumentumokba nem kerül valódi jelszó, kulcs, név, személyes pénzügyi adat vagy bérpapír-adat. Környezeti változónak csak a neve szerepelhet, és a példák összegei kitaláltak.

## Ellenőrzőlista

- [ ] A frontmatter, a H1 és a hivatkozássor megvan, a `[[wikilink]]`-ek létező fájlra mutatnak
- [ ] Az SP-k összege egyezik: story-k → epic-fejléc, epicek → a bevezető összege, sprint jegyei → `story_pont`
- [ ] A dátumok egyeznek a sprint-táblázattal és a Gantt-ábrával
- [ ] A FIN-kulcsok egyediek, a függőségek létező jegyekre mutatnak, és nem mutatnak későbbi sprintre
- [ ] A módosítás végig van vezetve a kapcsolódó dokumentumokon
- [ ] Az új külső tényeknek van forrásuk
- [ ] A mermaid-ábrák szintaktikailag helyesek, és egyeznek a szöveggel
- [ ] A szóhasználat egyezik a fenti táblázattal
