# 0007 Két olvasat, 1400 pixeles bemenet

**Állapot:** elfogadva

**Dátum:** 2026-10-31

## Kontextus

A FIN-408 hozza be a modellt a workerbe. A mérés a [[0006-blokkbeolvasas-a-pi-elott|ADR 0006]] után készült fotószerű, kitalált képeken, és két dolgot mutatott. A futási idő a kép méretével erősen nő: az ADR 0006-ban leírt kb. 20 másodperc csak kis képre igaz. A JSON módú kimenet pedig nem megbízható: ugyanarra a blokkra négyféle végösszeg jött, a szöveges mód viszont minden mintán helyes volt, csak az `Ő` lett `Ö`.

## Döntés

A worker minden képet kétszer olvas ki, JSON-sémával és szövegként, és mindkét eredményt a `bronze.extraction` táblába teszi. A modell 1400 pixel hosszú oldalú JPEG-et kap, az eredeti fájl változatlanul a Garage-ban marad. A részletek: [[Sprint 3]].

A rossz kimenet is a bronzba kerül, és a tétel lezárul. Csak a kapcsolati hiba hagyja nyitva a tételt, mert a modell újrafuttatása CPU-n percekbe kerül, és egy rossz kép percenként újra elindítaná.

## Elvetett alternatívák

- **Csak JSON mód:** feleannyi idő, de a végösszeg és a fizetési mód megbízhatatlan, és ez utólag nem pótolható, ha a kép már csak a Garage-ban van.
- **Csak szöveges mód:** pontos, de a tételeket és az árakat magyar blokkokra saját feldolgozóval kellene kinyerni, ez a FIN-402 kérdése.
- **2000 pixel:** kb. 190 másodperc olvasatonként, és a mintákon nem volt pontosabb az 1400 pixelnél.
- **1000 pixel:** kétszer gyorsabb, de a valódi fotón a blokk a képnek csak egy része, ezért túl kicsik lehetnek a betűk.

## Következmények

- Egy fotó feldolgozása a laptopon kb. 2,5–3,5 perc az ADR 0006-ban írt 20 másodperc helyett. Ez a tételeket sorban feldolgozó workernél elfogadható, de 20–30 blokknál már órás futás.
- Az 1400 pixel kitalált képekre alapul, ezért a saját fotókon mérni kell, és a FIN-407 felülírhatja.
- A FIN-404 a szöveges olvasatból veheti a végösszeget, a tételeket pedig a JSON-ból.
