# 0010 PDF-olvasás és külön számlafeldolgozó

**Állapot:** javasolt

**Dátum:** 2026-11-01

## Kontextus

A feltöltés ma csak képet fogad el, pedig a PDF-számla az [[Üzleti koncepció]] szerint forrás, és a FIN-307 e-mailes számlái is PDF-ek lesznek. A Technikai terv leírta az olvasás elvét, de egyetlen story sem építette meg.

2026-11-01-én négy dokumentum érkezett tömeges feltöltéssel: két A4-es számla, egy szállítólevél és egy új formátumú blokk. A modell mindegyiket olvashatóan, kb. 70–100 másodperc alatt adta vissza, a szöveges olvasatban a szerkezet megmaradt. Mind a négy `unparsed` lett, mert a feldolgozó csak az ismert blokksorokat kezeli, tehát rossz adat nem került be.

A két számla két különböző táblázatot használ: az egyik egy sorban adja a tételt, a másik minden cellát külön sorban. A felcímkézett mezők viszont mindkettőnél megvannak: adószám, sorszám, teljesítés dátuma, végösszeg.

## Döntés

- **PDF:** a worker a [pypdfium2](https://pypi.org/project/pypdfium2/) könyvtárral olvassa a szövegréteget. Ha nincs szövegréteg, ugyanezzel képpé alakítja a lapokat, és a modell olvassa el őket. Mindkét út `ocr_text` szöveget ad, így a feldolgozó nem tudja, honnan jött.
- **Számla:** külön szabályalapú feldolgozó készül a szöveges olvasatra, az [[0009-szabalyalapu-blokkfeldolgozo|ADR 0009]] elve szerint. A kimenete a `bronze.receipt_parse` táblába kerül, a `payload` `document_type` mezőjével.
- **Felismerés:** a dokumentum típusát a szöveg dönti el, nem a feltöltés módja, így a számla fotóról, PDF-ből és később e-mailből is ugyanoda jut.
- **Tételek sorrendje:** előbb a felcímkézett mezők, utána a táblázat. Ismeretlen táblázatnál a számla `review` lesz a végösszeggel, nem `unparsed`, és nem talál ki tételt.
- **Szállítólevél:** nem kiadás, ezért a felismerés nem veszi számlának, és nem kap tételeket. Különben a hozzá tartozó számlával kétszer számolódna.
- **Adatvédelem:** a vevő neve és címe csak a nyers szövegben marad, a feldolgozott adatba nem kerül be.

## Elvetett alternatívák

- **pypdf:** csak szöveget olvas ([forrás](https://pypi.org/project/pypdf/)), a szkennelt PDF-hez második eszköz kellene. A pypdfium2 egy függőségként mindkettőt adja.
- **pdfplumber:** a táblázatot jól bontja, de csak szövegréteggel működik. A fotózott számlához külön kódág kellene, ezért a szabályok két helyen élnének.
- **Minden PDF képként a modellhez:** oldalanként kb. másfél perc, és a szövegréteg biztos számjegyei helyett modellolvasat lenne.
- **Számla a blokkfeldolgozóban:** a két szerkezet szabályai rontanák egymást, és a meglévő blokkok eredménye is változhatna.
- **Nyelvi modell a számlára:** ugyanaz a párosítási kockázat, mint az ADR 0009-ben, és percekbe kerülne CPU-n.

## Következmények

- A workerbe új függőség kerül, a PDFium binárissal együtt. Licence BSD-3-Clause és Apache-2.0 ([forrás](https://pypi.org/project/pypdfium2/)).
- A szövegréteg sorrendje nem mindig a látható sorrend. Ezt saját PDF-en mérni kell, és ha kell, a sorokat a karakterek helyéből kell felépíteni.
- A számláknál az elrendezés jobban változik, mint a blokkoknál, ezért a tételek aránya lehet gyengébb. A végösszeg, a dátum és a szállító ettől függetlenül megvan.
- A tábla neve `receipt_parse` marad. Átnevezni nem érdemes, mert a bronz csak bővül, a FIN-406 pedig a `document_type` szerint választ.
- A FIN-307 ugyanezt az olvasást használja, ezért az e-mailes számlához csak a lehúzás hiányzik.
