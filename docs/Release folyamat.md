---
projekt: Pénzügyi nyomkövető
tipus: release folyamat
datum: 2026-10-31
tags: [penzugy, projekt, release]
---

# Release folyamat

Kapcsolódó: [[Változásnapló]] · [[Fejlesztési terv]] · [[Technikai terv]]

Sprintenként egy kiadás készül, a sprint végi demó napján. A változásokat folyamatosan a [[Változásnapló]] gyűjti, a kiadás pedig egy `main` ágon lévő verziócímke, amelyből a GitHub Release automatikusan elkészül. Mivel az éles rendszer otthon fut, a címke önmagában semmit nem telepít: a telepítés külön, kézi lépés.

## Verziózás

A verziók `vMAJOR.MINOR.PATCH` formájúak.

| Kiadás | Mikor | Példa |
| --- | --- | --- |
| Minor | Sprint végén, ha a `main` változott | S1 vége: `v0.1.0` |
| Patch | Sürgős javítás két sprint között | `v0.1.1` |
| `v1.0.0` | Első éles használat, a 6. sprint vége (2027-01-24) | `v1.0.0` |
| Major | `v1.0.0` után, ha a frissítéshez kézi adatművelet kell | `v2.0.0` |

Ha egy sprintben a `main` nem változott, nincs kiadás.

## Változásnapló vezetése

- **Ki és mikor:** aki pull requestet nyit, az a saját változását ugyanabban a pull requestben beírja a `## Kiadatlan` rész alá.
- **Mi kerül bele:** ami a szoftver működését, a telepítést vagy a biztonságot érinti. A belső átfogalmazás és a tisztán dokumentációs változás nem.
- **Forma:** egy sor, a jegy kulcsával kezdve, ha van: `- FIN-301 Tailscale a Pi-n.`
- **Nyilvános szöveg:** a napló a GitHub Release-be is bekerül, ezért valódi adat, név és összeg nem szerepelhet benne.
- **Kiadott rész:** ami már verziószám alatt van, az nem módosul; a tévedést a következő kiadás javítja.

A bejegyzések ezek alá a címsorok alá kerülnek, és ami üres, az elmarad:

| Címsor | Mi tartozik ide |
| --- | --- |
| `### Hozzáadva` | Új képesség |
| `### Módosítva` | Meglévő működés változása |
| `### Javítva` | Hibajavítás |
| `### Eltávolítva` | Megszűnt képesség |
| `### Biztonság` | Biztonságot érintő változás |
| `### Frissítési teendők` | Amit telepítéskor kézzel kell megtenni, pl. új `.env`-változó |

## Kiadás lépései

1. **Ellenőrzés:** a sprint jegyei merge-ölve vannak, a CI zöld a `main` ágon, a Kiadatlan rész teljes.
2. **Előkészítés:** a script létrehozza a `release/v0.1.0` ágat, és a Kiadatlan részt verzióvá alakítja.
   ```sh
   scripts/release.sh prepare 0.1.0
   git add -A
   git commit -m "Kiadás: v0.1.0"
   git push -u origin release/v0.1.0
   ```
3. **Pull request:** a CI zöld, a kiadás szövege át van nézve, majd merge.
4. **Címke:** a frissített `main` ágon a script elkészíti és felküldi a címkét.
   ```sh
   git switch main
   git pull
   scripts/release.sh tag 0.1.0
   ```
5. **GitHub Release:** a címke elindítja a `Release` workflow-t, amely a [[Változásnapló]] megfelelő részéből létrehozza a kiadást. Ha a címke nincs a `main` ágon, a workflow hibával leáll.

## Telepítés az otthoni stackre

A frissítés előtt mindig készül mentés. Előtte nézd át a kiadás `Frissítési teendők` részét.

```sh
scripts/backup.sh
git fetch --tags
git checkout v0.1.0
podman compose -f home/docker-compose.yml up -d
podman compose -f home/docker-compose.yml run --rm migrate
scripts/test-bronze.sh
```

A Metabase-t a demó előtt nyisd meg, és nézd át a fő dashboardot: a bronz teszt csak az adatbázist ellenőrzi.

## Visszaállás

- **Kód:** `git checkout` az előző címkére, majd `podman compose -f home/docker-compose.yml up -d`.
- **Migráció:** a bronz migrációk nem görgethetők vissza, ezért hibás migrációt új patch-kiadás javít. A migrációk csak bővítik a sémát, így a korábbi kód tovább működik.
- **Adat:** csak adatvesztésnél kell a restic mentéshez nyúlni, a README „Mentés” része szerint.

## Sürgős javítás

A patch-kiadás is pull requesten megy át, a `main` ágról indítva. Telepített kiadás hibája esetén a javítás a `main` ágra kerül, majd a Kiadás lépései `0.1.1` verzióval futnak le. Külön karbantartási ág nincs, mert egyetlen telepített példány van.
