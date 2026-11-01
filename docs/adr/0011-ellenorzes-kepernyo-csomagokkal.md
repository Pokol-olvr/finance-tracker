# 0011 Ellenőrzés képernyő visszatöltött csomagokkal

**Állapot:** javasolt

**Dátum:** 2026-11-01

## Kontextus

A `review` ma csak jelölés: a dokumentumot nem lehet jóváhagyni vagy javítani, és az eredetit sem látni a feldolgozott adatok mellett. A kép a lezáráskor törlődik a postaládából, utána csak a Garage-ban van, a feldolgozott adat pedig csak a bronzban.

A webapp most a laptopon fut, de a FIN-308 után a Pi-re költözik, ahonnan sem a Garage, sem a Postgres nem érhető el, és minden kapcsolatot az otthoni oldal nyit. A képernyőnek akkor is működnie kell, ha a laptop ki van kapcsolva.

Az `ok` dokumentumot is látni kell az eredeti mellett: a FIN-410 és a FIN-412 mérése azt nézi, egyezik-e a papírral.

## Döntés

A worker ellenőrzési csomagot tölt vissza a webappnak: a fájlt, a feldolgozott adatokat, az ellenőrzéseket és a szöveges olvasatot. A webapp csak ebből dolgozik, a bronzot és a Garage-ot nem olvassa.

- **Egy út mindenre:** a worker körönként összeveti a bronzot a csomagokkal, és pótolja, ami hiányzik vagy régi. Így az új, az újrafeldolgozott és a korábban lezárt dokumentum ugyanazon az úton jut a képernyőre, külön visszatöltő eszköz nélkül.
- **A sor nem változik:** a postaláda tétele a feldolgozás után ugyanúgy lezárul, a fájlja törlődik. A csomag külön tárolódik, a saját fájljaival.
- **Megőrzés:** a csomag döntésig marad, a lezárt dokumentumé a döntés vagy a feldolgozás után 30 napig. A régebbi `ok` dokumentumot a worker nem tölti vissza.
- **Döntés:** a webapp a saját SQLite-jában tárolja, a worker húzza le a `bronze.review_decision` táblába, majd nyugtázza. A bronz többi táblája nem változik.
- **Előnézet:** a HEIC fájlt a böngészők nem jelenítik meg, ezért ilyenkor a worker a modellnek készült JPEG-et tölti vissza. Az eredeti a Garage-ban változatlan marad.

## Elvetett alternatívák

- **A webapp olvassa a bronzot és a Garage-ot:** itt a laptopon ez a leggyorsabb, de a Pi-ről nem működne, és a FIN-308-nál újra kellene írni.
- **A fájl nyitva marad a postaláda tételén:** a korábbi terv ez volt, a [[Sprint 3]] is ezt írta. Ez megváltoztatná a tétel életútját, a több képes blokkoknál külön kezelést kérne, a már lezárt dokumentumokhoz és a HEIC-hez pedig így is kellene visszatöltés. Két út lenne egy helyett.
- **Letöltés kérésre:** a webapp a megnyitáskor kérné a fájlt a workertől. A Pi nem nyithat kapcsolatot hazafelé, és kikapcsolt laptopnál a képernyő üres lenne.
- **Csak a `review` dokumentumok csomagja:** egyszerűbb, de az `ok` dokumentumot nem lehetne összevetni a papírral.
- **Végleges megőrzés a webappnál:** a Pi postaláda, nem végleges tár. A személyes adat itt ne legyen tovább a szükségesnél, a fájl a Garage-ban úgyis megvan.

## Következmények

- A worker minden fájlt még egyszer feltölt a webappnak. A Pi-n ez az otthoni feltöltési sebességtől függ, ezt a FIN-308 után mérni kell.
- A Pi lemezén legfeljebb 30 napnyi dokumentum és szöveges olvasat lesz, a vevő nevével együtt. Ez csak a Tailscale és az Authelia mögött látszik, ezért a FIN-303 előtt az oldal nem nyitható ki a helyi gépről.
- A döntés csak a bronzba jut el. A javított érték a FIN-406-tal jelenik meg a silverben, addig a Metabase nem mutatja.
- A döntés a képernyőn nem módosítható. A bronz ettől még több döntést is elbír, a FIN-406 a legutóbbit veszi.
- A parser javítása után a nyitott `review` dokumentum magától lezárulhat, ha az új verzióval `ok` lesz. A már meghozott döntést az újrafeldolgozás nem írja felül.
