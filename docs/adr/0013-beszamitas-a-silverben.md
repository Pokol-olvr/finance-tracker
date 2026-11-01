# 0013 Beszámítás a silverben: döntés utáni dokumentumok és a javítás helye

**Állapot:** elfogadva

**Dátum:** 2026-11-01

## Kontextus

A FIN-406-tal a bronz dokumentumaiból kiadás lesz. Egy dokumentumhoz több feldolgozás és több döntés is tartozhat, és a Sprint 4 óta van `review`, `unparsed`, nem kiadás, elvetett, újranyitott és javított állapot. Ki kell mondani, melyik számít a havi kiadásba, különben ugyanaz a dokumentum más-más számot adna a modellekben.

A Technikai terv korrekciós táblát ígért a silverbe. A javítás viszont a FIN-405 óta a `bronze.review_decision` táblában van, a `corrected` mezőben, a döntést hozó személlyel és az időponttal együtt.

A tételenkénti besorolás a FIN-502-vel, a Sprint 7-ben jön. Addig a 13 tárolt dokumentumból 4 két címkét kapott, és ezeknél nem lehet tudni, melyik tétel melyikhez tartozik.

## Döntés

- **Beszámítás:** a kiadásba csak a rendben lévő, jóváhagyott vagy javított dokumentum számít. Az ellenőrzésre váró, a nem kiadás és az elvetett dokumentum nem, az újranyitott pedig addig nem, amíg nincs új döntés, kivéve, ha az olvasata `ok`.
- **Egy igazság:** a beszámítást egyetlen silver modell, a `documents` dönti el, minden más modell ebből olvas.
- **Javítás:** a `bronze.review_decision` a korrekciós tábla, külön tábla nem készül. Dokumentumonként a legutóbbi döntés érvényes.
- **Kategória sorrendje:** szabály, a dokumentum egyetlen címkéje, végül `besorolatlan`.
- **Besorolatlan:** technikai érték, nem kategória. A feltöltésnél nem választható, és a `categories` seedbe sem kerül, mert azt a webapp is olvassa.
- **Duplikátum:** azonos adószám és sorszám esetén csak a legkorábbi dokumentum számít.

## Elvetett alternatívák

- **A függő dokumentum jelölve beszámít:** a kiadás hamarabb látszana, de egy hibás olvasat összege a havi számokba kerülne. A függő dokumentumok száma az állapotoldalon úgyis látszik.
- **Külön korrekciós tábla:** ugyanazt tárolná másodszor, és két helyen kellene eldönteni, melyik az érvényes.
- **Az első címke alá sorolás:** nincs külön sor, de a kategóriák csendben torzulnak.
- **Arányos szétosztás a címkék között:** kitalált számokat adna, amelyeket semmi nem igazol.

## Következmények

- A havi összeg alacsonyabb lehet, amíg van döntésre váró dokumentum.
- A `transactions_expense_has_known_category` teszt elfogadja a `besorolatlan` értéket, de külön teszt figyeli az arányát.
- A nem forintos számla jóváhagyással nem kerül a kiadások közé, csak forintra javítva, mert a silver csak forintot tart.
- A FIN-502 után a `besorolatlan` tételek a kérdések közé kerülnek, és az arányuk csökken.
