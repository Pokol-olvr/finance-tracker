# 0014 Streamlit riportfelület a Metabase helyett

**Állapot:** javasolt

**Dátum:** 2026-11-01

## Kontextus

A Metabase felülete a napi használatban nem intuitív: általános elemzőeszköz, és a kész számok mellett a szerkesztési lehetőségeit is mutatja. A nyílt forrású kiadásban a szín, a logó, a betűtípus és az alkalmazás neve nem módosítható, ezek Pro vagy Enterprise csomagot kérnek ([forrás](https://www.metabase.com/docs/latest/configuring-metabase/appearance)). Beágyazva marad a „Powered by Metabase” sáv ([forrás](https://www.metabase.com/articles/is-metabase-embedding-free)).

Az [[Üzleti koncepció]] nehezebb részei nem diagramok: mondatban megfogalmazott javaslat a befizetés emelésére, what-if számítás és lefúrás a blokk eredetijéig. Ezek saját oldalakon természetesek, BI-eszközben nehézkesek.

Egy eldobható próba 2026-11-01-én három oldalt épített meg a saját adatokon: működött a felső menü, a csúszkás what-if, a mondatos javaslat és a lefúrás az Ellenőrzés képernyőig. Használat közben kb. 140 MB memóriát foglalt, a futó Metabase kb. 1,5 GB-ot.

## Döntés

A riportfelület Streamlitben készül, és a Metabase kikerül a stackből.

- **Adat:** a Streamlit csak a goldot olvassa, saját, csak olvasási jogú szerepkörrel. A javaslatok és a számítások a goldban vagy az oldal kódjában vannak, adatbevitel nincs benne.
- **Hely:** az otthoni stackben fut a gold mellett, a Pi-re nem költözik.
- **Adatvédelem:** a használati statisztika ki van kapcsolva, és a `browser.serverAddress` beállítása megakadályozza, hogy induláskor külső szolgáltatástól kérdezze a nyilvános IP-címet.
- **Kivezetés:** a Metabase csak azután kerül ki, hogy az új Áttekintés ugyanazokat a számokat adja.

## Elvetett alternatívák

- **Metabase hangolva:** ingyenes, de a külseje nem változtatható, és a mondatos javaslat nehézkes marad.
- **Metabase a Streamlit mellett:** megmaradna a szabad elemzés, de két rendszert kellene üzemeltetni, és a Metabase kb. 1,5 GB memóriát foglal.
- **Apache Superset:** a 6.0-tól ingyen témázható ([forrás](https://superset.apache.org/admin-docs/configuration/theming/)), de ugyanaz az elemzőfelület, csak bonyolultabb, és Redis és Celery is kell mellé.
- **Lightdash:** a hivatalos telepítési útmutató Kubernetes-klasztert kér ([forrás](https://docs.lightdash.com/self-host/self-host-lightdash)).
- **Evidence:** a fejlesztése a fizetős Studio felé tolódott, az npm-csomagja 2026 februárja óta nem frissült.
- **Saját oldalak a webappban:** a legtöbb munka, és a Pi-re költöző webapp nem éri el a goldot.

## Következmények

- Nincs kattintgatós elemzés: minden új nézet kódmódosítás. Eseti kérdéshez az adatbázist közvetlenül kell lekérdezni.
- A dashboardokat nem lehet a felületen átrendezni, viszont verziókezeltek és tesztelhetők.
- A hónap közbeni adatok csak azt mutatják, amit a gold tartalmaz, ezért a Közös háztartás fülhöz a közös kassza gold táblája kell (E6).
- A diagramok Altairrel készülnek, mert a beépített diagramok ezres tagolása nem állítható magyarra.
- Az oldalon nincs belépés, ezért a szolgáltatás csak helyben érhető el, amíg a külső elérés nincs megoldva.
- A `metabase` adatbázis, a `metabase_owner` szerepkör és az `MB_*` beállítások kikerülnek, a mentés is egyszerűsödik.
