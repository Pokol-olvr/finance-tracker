---
projekt: Pénzügyi nyomkövető
tipus: változásnapló
datum: 2026-10-31
tags: [penzugy, projekt, release]
---

# Változásnapló

Kapcsolódó: [[Release folyamat]] · [[Fejlesztési terv]]

Minden, a szoftvert érintő változás ide kerül, a kiadáskor pedig innen készül a GitHub Release szövege. A vezetés szabályai: [[Release folyamat]].

## Kiadatlan

### Hozzáadva

- FIN-101 Repó, mappaszerkezet, README, ADR-sablon és az első két ADR.
- FIN-102 Otthoni Compose rögzített verziókkal: Postgres 18.6, Garage 2.5.0, Metabase 0.65.2.4.
- FIN-201 Bronz séma `raw_document`, `extraction` és `manual_entry` táblákkal; a réteg csak hozzáfűzhető.
- FIN-201 Üres silver és gold séma, szerepkörök és jogok.
- FIN-103 A Metabase saját adatai a Postgresben, és a `scripts/metabase-setup.sh` az első beállításhoz.
- FIN-104 Napi mentés resticcel, a `scripts/restore-test.sh` visszaállítási próbával.
- FIN-105 CI: lint, Compose-ellenőrzés, migrációk, bronz teszt és titokkeresés.
- Release folyamat, változásnapló és automatikus GitHub Release.

### Biztonság

- Adatfájlok tiltása a repóban, commit előtti titokkereséssel, mert a repó nyilvános.
