# 0016 A csonka olvasás újraolvasása

**Állapot:** elfogadva; az [ADR 0012](0012-ujranyitas-az-ujraolvasas-helyett.md) kivétele

**Dátum:** 2026-11-17

## Kontextus

Az ADR 0012 szerint nincs újraolvasás, mert ugyanarra a fájlra ugyanaz a beállítás ugyanazt adja. 2026-11-17-én két saját fotó olvasása a blokk közepén megszakadt: a 2000 px-es kép kb. 3 800 tokent foglalt az Ollama 4096 tokenes alapkontextusából, a szövegnek kb. 260 maradt. A bronzban a `done_reason` értéke `length` lett, a blokk `unparsed`. A fájl ugyanaz maradt, újrafeltöltéskor „már megvolt” az eredmény, pedig a nagyobb kontextussal a teljes szöveg kijön.

## Döntés

- **Kontextus:** a kérés `num_ctx` értéke 8192, a `PROMPT_VERSION` 3.
- **Újraolvasás:** a worker induláskor újraolvassa azt a dokumentumot, amelynek a legutóbbi olvasása `length` miatt szakadt meg, és régebbi `PROMPT_VERSION`-nel készült. A fájlt a Garage-ból veszi, az új olvasás új sor a bronzban, a régi megmarad.
- **Feldolgozás:** a feldolgozás a legutóbbi olvasást veszi, ezért a `PARSER_VERSION` emelésével a csoport újra feldolgozódik.

## Elvetett alternatívák

- **Újraolvasó gomb:** az ADR 0012 indoka továbbra is áll a nem csonka olvasásra; a csonka olvasás felismerhető, nem kell hozzá döntés.
- **Minden olvasás újra beállításváltáskor:** a 17 blokk GPU-n 39 másodperc, CPU-n kb. 50 perc, és a nem csonka olvasás nem változna.
- **Az adatok törlése és újrafeltöltés:** működik, de a bronz csak hozzáfűzhető, és élesben a FIN-309 után ez már nem járható.

## Következmények

- Ugyanazzal a beállítással csonka olvasás nem fut újra, így nincs végtelen ciklus.
- A `bronze.extraction` `created_at` mezője a tényleges beszúrási idő, így egy tranzakción belül is a legutóbbi olvasás nyer.
