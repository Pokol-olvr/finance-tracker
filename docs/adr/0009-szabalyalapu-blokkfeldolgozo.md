# 0009 Szabályalapú blokkfeldolgozó a szöveges olvasatra

**Állapot:** elfogadva

**Dátum:** 2026-11-01

## Kontextus

Az [[0007-ket-olvasat-1400-pixelen|ADR 0007]] szerint a tételek a JSON-olvasatból, a végösszeg a szöveges olvasatból jött volna. Ez kitalált képeken készült. Az első saját blokkon a JSON-olvasat rosszul párosította a neveket és az árakat, a tételei nem adták ki a végösszeget, és a végösszege sem szerepelt a szöveges olvasatban.

Ugyanitt a szöveges olvasatban minden szám helyes volt: a tételek, a mennyiségek, a végösszeg, a fizetett összeg és a visszajáró is, és a blokk ezekből önmagát igazolta. A sorszerkezet is megmaradt. Az ékezetek viszont hibásak voltak. Ez egyetlen blokk, ezért a FIN-410 mérése ellenőrzi.

## Döntés

A modell csak szöveget olvas, a szerkezetet saját, szabályalapú feldolgozó adja a szöveges olvasatból. A JSON-olvasat kikerül, ezzel az ADR 0007 kétolvasatos döntése megszűnik, az 1400 pixeles bemenet marad. A feldolgozó kimenete a `bronze.receipt_parse` táblába kerül a saját verziójával, és a nyers szövegből modell nélkül újrafuttatható.

A blokk csak akkor számít rendben lévőnek, ha az ellenőrzései sikeresek. Az ékezeteket nem írjuk vissza: az egyeztetés ékezet nélkül történik, a boltot az adószám azonosítja. A részletek: [[Sprint 4]].

## Elvetett alternatívák

- **JSON-olvasat megtartása:** érvényes JSON-t ad, de a párosítás hibája csendes, és a modell nem tudja megmondani, hol tévedett. Kétszeres futási időbe is kerül.
- **Másik modell a szövegre:** a szövegből JSON-t kérni egy nyelvi modelltől ugyanazt a párosítási kockázatot hozná vissza, percekbe kerülne CPU-n, és nem lenne ismételhető úgy, mint egy szabály.
- **Nagyobb kép:** a számok már 1400 pixelen helyesek voltak, a JSON hibája pedig nem olvasási hiba volt.
- **PaddleOCR most:** új, nehéz függőség egy olyan hibára, amely a szöveges olvasatban nem jelentkezett. A FIN-403 feltételes lett, a FIN-410 dönt róla.
- **Tartalékmodell:** a Qwen3-VL a kitalált blokkokon rosszabbul olvasta a számokat, és a JSON párosítási kockázata ott is megmaradna.

## Következmények

- Egy blokkhoz egy modellhívás kell, ezért a feldolgozás várhatóan a felére rövidül. Ezt mérni kell.
- A feldolgozó ismételhető és tesztelhető, kitalált blokkokkal.
- Minden új blokkformátumhoz szabály kell. Ha egy bolt formátuma ismeretlen, a blokk `review` vagy `unparsed` lesz, és nem kerül rossz adat a tételek közé.
- A szabályok javítása után a régi blokkok modell nélkül újra feldolgozhatók.
- Az ADR 0006 FIN-801–804 feltétele marad: finomhangolás csak akkor kell, ha a szöveges olvasat a saját blokkokon gyenge.
