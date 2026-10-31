# 0005 Monorepó és átmeneti otthoni webapp

**Állapot:** elfogadva

**Dátum:** 2026-10-31

## Kontextus

A [[Technikai terv]] szerint a webapp a Pi-n fut, SQLite-tal, és csak a worker ír a bronzba. A kézi bejegyzés API viszont a 2. sprintben készül, amikor sem a Pi, sem a worker nincs meg. Azt is el kell dönteni, hogy a Pi kódja külön repóba kerül-e.

## Döntés

Egy repó marad: a `webapp/` a kód, a `pi/` a Pi Compose-fájlja, a Pi-n ugyanez a repó van klónozva. Amíg a Pi nincs beállítva, a webapp az otthoni stackben fut, csak helyben elérhetően, és közvetlenül a bronzba ír.

## Elvetett alternatívák

- **Külön repó a Pi-nek:** a webapp és az otthoni stack közös szerződése (bronz mezők, kiadás) két helyen élne, és két repót kellene együtt kiadni.

## Következmények

- Egy verziócímke írja le a teljes rendszert, a Pi-n és otthon ugyanazt a címkét kell telepíteni.
- A bronz írása egyetlen modulban van (`webapp/app/store.py`), a Pi-re költözéskor ez cserélődik a postaládára.
- Költözés után az `app_writer` a webapp helyett csak a workernél marad.
