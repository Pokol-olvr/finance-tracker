---
projekt: Pénzügyi nyomkövető
sprint: S6
kezdes: 2027-01-11
vege: 2027-01-24
story_pont: 16
tags: [penzugy, sprint]
---

# Sprint 6

Vissza: [[Fejlesztési terv]]

## Sprint cél

**A webapp a Pi-re költözik, telefonról is elérhető, de csak a Tailscale-hálózatról, HTTPS-sel és kétfaktoros belépéssel. A továbbított e-mailes számla magától a bronzba kerül. A sprint végén a `finance` adatbázis üresen újraépül, és indul az éles használat.** A sprint 2027-01-11 és 2027-01-24 között tart, 16 story ponttal.

| Kulcs | Jegy | SP | Függ tőle |
| --- | --- | --- | --- |
| FIN-301 | Tailscale a Pi-n, a telefonokon és az otthoni gépen | 2 | – |
| FIN-302 | Caddy HTTPS a saját domainen | 2 | FIN-301 |
| FIN-303 | Authelia TOTP 2FA két felhasználóval | 3 | FIN-302 |
| FIN-308 | Webapp és postaláda költözése a Pi-re | 3 | FIN-301, FIN-302, FIN-303 |
| FIN-307 | E-mailes számlafogadás | 5 | FIN-312 |
| FIN-309 | A `finance` adatbázis üres újraépítése | 1 | FIN-308, FIN-307 |

Javasolt sorrend: FIN-301, FIN-302, FIN-303, FIN-308, FIN-307, FIN-309. A hálózat, a tanúsítvány és a belépés egymásra épül, ezért elöl vannak, és a FIN-308 csak ezek után költözteti a webappot. A FIN-307 a workerben fut, ezért a Pi-től függetlenül is haladhat, ha a Pi-s rész elakad. A FIN-309 az utolsó, mert utána már csak valódi adat kerül a rendszerbe.

**Előfeltétel:** a `v0.5.0` kiadva és az otthoni stackre telepítve. A Sprint 4 nyitott, saját számlás pontjai (FIN-412, FIN-312) a FIN-307 első valódi számlájával lezárhatók.

**Változás a tervhez képest:** az otthoni stack 2026-11-16 óta Windowson, WSL2-ben is fut, RTX 5070 GPU-val. A Technikai terv a laptopot nevezi meg otthoni gépnek; hogy melyik gépen fusson tartósan, a tervezésen dől el (lásd lent).

**Adat:** a Pi és az e-mail beállításai, a domain, a címek és a titkok csak a `.env`-ekbe kerülnek, a repóba nem. A tesztekhez kitalált levelek és címek kellenek.

## FIN-301 Tailscale a Pi-n, a telefonokon és az otthoni gépen · 2 SP

**Story:** felhasználóként a telefonomról akarom elérni a webappot, hogy ne kelljen a fotót a laptopra áttenni, de kívülről senki ne lássa.

**Részfeladatok**

- [ ] Tailscale a Pi-n, a két telefonon és az otthoni gépen, egy tailnetben 📅 2027-01-24
- [ ] ACL: a telefonok csak a Pi webappját érik el, az otthoni gép a Pi-t és a saját szolgáltatásait 📅 2027-01-24
- [ ] WSL-es otthoni gépnél: a Tailscale a Windows-oldalon fut, a WSL portjai a Tailscale-címen is látszanak; ha nem, a `BIND_ADDRESS` a megoldás 📅 2027-01-24
- [ ] A Pi-n nincs nyitott bejövő port a routeren 📅 2027-01-24

**Elfogadási feltételek**

- [ ] A webapp csak a Tailscale-hálózatról érhető el
- [ ] Mobilnetről, Tailscale nélkül a Pi címe nem válaszol
- [ ] Az otthoni gép a Pi-t a Tailscale-címén éri el

## FIN-302 Caddy HTTPS a saját domainen · 2 SP

**Story:** felhasználóként érvényes HTTPS-t akarok, hogy a böngésző ne figyelmeztessen, és a PWA a kamerát is elérje.

**Részfeladatok**

- [ ] Caddy a `pi/` Compose-ban, a DNS-szolgáltató pluginjával 📅 2027-01-24
- [ ] DNS-alapú ACME-ellenőrzés, mert az oldal kívülről nem látszik 📅 2027-01-24
- [ ] Belső DNS-rekord a Pi Tailscale-címére, vagy Tailscale MagicDNS 📅 2027-01-24
- [ ] A DNS API-kulcs csak a Pi `.env`-jében, a lehető legszűkebb joggal 📅 2027-01-24

**Elfogadási feltételek**

- [ ] Érvényes tanúsítvány, a böngésző nem figyelmeztet
- [ ] A tanúsítvány megújul emberi beavatkozás nélkül (a Caddy naplója mutatja)
- [ ] HTTP-ről HTTPS-re irányít

## FIN-303 Authelia TOTP 2FA két felhasználóval · 3 SP

**Story:** felhasználóként második faktort akarok a belépéshez, hogy egy elveszett, de a tailnetbe belépett telefon se legyen elég.

**Részfeladatok**

- [ ] Authelia a `pi/` Compose-ban, fájlalapú felhasználókkal, a Caddy `forward_auth` mögött 📅 2027-01-24
- [ ] Két felhasználó a `HOUSEHOLD_MEMBERS` kódjaival, TOTP-vel 📅 2027-01-24
- [ ] A worker API (`/inbox/…`) Authelia nélkül, csak a `WORKER_API_TOKEN`-nel érhető el 📅 2027-01-24
- [ ] A webapp a belépett felhasználót a fejlécből veszi, így a feltöltő nem választható szabadon 📅 2027-01-24
- [ ] Munkamenet-idő és kizárás túl sok hibás próbálkozás után 📅 2027-01-24

**Elfogadási feltételek**

- [ ] Második faktor nélkül nincs hozzáférés
- [ ] A worker token nélkül nem éri el az API-t, tokennel 2FA nélkül is
- [ ] A feltöltő mindig a belépett felhasználó

## FIN-308 Webapp és postaláda költözése a Pi-re · 3 SP

**Story:** felhasználóként a Pi-re akarom költöztetni a webappot, hogy a feltöltés akkor is működjön, ha az otthoni gép ki van kapcsolva.

**Részfeladatok**

- [ ] `pi/docker-compose.yml`: webapp, Caddy, Authelia; az adat a Pi `DATA_DIR`-jében 📅 2027-01-24
- [ ] A webapp ARM-képe a Pi-n épül 📅 2027-01-24
- [ ] Az otthoni worker `INBOX_URL`-je a Pi Tailscale-címére mutat, minden kapcsolatot az otthoni oldal nyit ([[0006-blokkbeolvasas-a-pi-elott|ADR 0006]]) 📅 2027-01-24
- [ ] Az otthoni Compose-ból kikerül a webapp; az állapot képernyő a Pi-n marad, a jelentést az otthoni gép küldi ([[0008-allapot-kepernyo-a-webappban|ADR 0008]]) 📅 2027-01-24
- [ ] A Pi postaládája a mentésbe nem kerül, csak átmeneti tároló 📅 2027-01-24
- [ ] A README telepítési része a Pi-vel 📅 2027-01-24

**Elfogadási feltételek**

- [ ] Telefonról feltölthető, a worker a Pi postaládájából húz
- [ ] Kikapcsolt otthoni gépnél a feltöltés a Pi-n vár, bekapcsolás után feldolgozódik
- [ ] Az Ellenőrzés, a Szabályok és a Betétdíj a Pi-n is működik

## FIN-307 E-mailes számlafogadás · 5 SP

**Story:** felhasználóként a webshopok számláit egy címre akarom továbbítani, hogy ne kelljen letölteni és feltölteni őket.

**Részfeladatok**

- [ ] Külön postafiók a levelezőszolgáltatónál, pl. `szamla@` a saját domainen 📅 2027-01-24
- [ ] Worker: IMAP-lehúzás titkosított kapcsolaton, a feldolgozott levél a „Feldolgozva” mappába kerül 📅 2027-01-24
- [ ] Csak a két saját feladótól, ellenőrzött SPF- és DKIM-eredménnyel 📅 2027-01-24
- [ ] Címkék a tárgyból (`#élelmiszer #háztartás`), a vásárló a továbbító 📅 2027-01-24
- [ ] A nyers `.eml` és a mellékletek a Garage-ba, a bronzban `email` forrástípussal (migráció) 📅 2027-01-24
- [ ] A PDF-melléklet ugyanazon az úton megy, mint a webes feltöltés ([[0010-pdf-olvasas-es-szamlafeldolgozo|ADR 0010]]) 📅 2027-01-24
- [ ] Kitalált levelekkel tesztek: idegen feladó, hamis DKIM, melléklet nélküli levél 📅 2027-01-24

**Elfogadási feltételek**

- [ ] Továbbított PDF-számla bekerül a bronzba, és megjelenik az Ellenőrzésen
- [ ] Idegen feladó levele nem kerül be, és a postafiókban marad
- [ ] Ugyanaz a levél kétszer nem kerül be
- [ ] A postafiók jelszava csak az otthoni `.env`-ben van

## FIN-309 A `finance` adatbázis üres újraépítése · 1 SP

**Story:** adatgazdaként üres adatbázissal akarom indítani az éles használatot, hogy a mock adat és a próbablokkok ne torzítsák a riportokat.

**Részfeladatok**

- [ ] Script: a stack leállítása, a Postgres, a Garage és a postaláda adatának törlése, újraindítás üresen; a modell megmarad 📅 2027-01-24
- [ ] A restic tároló újrakezdése, mert a régi pillanatképekben próbablokk is van 📅 2027-01-24
- [ ] Az új `RESTIC_PASSWORD` a jelszókezelőbe 📅 2027-01-24
- [ ] Az első valódi mentés és a `scripts/restore-test.sh` 📅 2027-01-24

**Elfogadási feltételek**

- [ ] A bronz és a Garage `raw` bucket üres
- [ ] A mock adat és a próbablokkok eltűntek a restic-pillanatképekből is
- [ ] A riportoldalak üres adattal is működnek
- [ ] Az első éles mentés visszaállítási próbája sikeres

## Események és nyitott kérdések

- [ ] Sprinttervezés, kb. 30 perc 📅 2027-01-11
- [ ] Heti áttekintés, kb. 15 perc 📅 2027-01-18
- [ ] Demó és retró, kb. 30 perc 📅 2027-01-24
- [ ] Kiadás: `v0.6.0` a [[Release folyamat]] szerint 📅 2027-01-24

**A tervezésen eldöntendő**

- [ ] Melyik gépen fut tartósan az otthoni stack: a Fedorás laptopon vagy a Windowsos gépen, WSL-ben, GPU-val? A WSL nyitott ablak nélkül egy idő után leáll, ezért a Windowsos gépen ezt külön kell megoldani 📅 2027-01-11
- [ ] A Pi típusa és rendszere; a webapp képe ARM-ra épül 📅 2027-01-11
- [ ] A domain és a DNS-szolgáltató, amelynek van API-ja a Caddy DNS-ellenőrzéséhez 📅 2027-01-11
- [ ] A levelezőszolgáltató és a `szamla@` postafiók; támogatja-e az IMAP-ot és az alkalmazásjelszót 📅 2027-01-11
- [ ] Tailscale vagy Headscale: a Headscale-hez a vezérlőszervernek kívülről elérhetőnek kell lennie 📅 2027-01-11

**Eldöntve a tervezés előtt**

- [x] Minden kapcsolatot az otthoni oldal nyit, a Pi-re és az otthoni hálózatba nem kell bejövő port ([[0006-blokkbeolvasas-a-pi-elott|ADR 0006]]).
- [x] A Tailscale marad a WireGuard helyett ([[0003-tailscale-a-wireguard-helyett|ADR 0003]]).
- [x] A riportfelület az otthoni stackben marad, a Pi-ről nem kell elérnie a goldot ([[0014-streamlit-a-metabase-helyett|ADR 0014]]).
- [x] Az e-mailes számla PDF-je ugyanazon a feldolgozón megy át, mint a feltöltött ([[0010-pdf-olvasas-es-szamlafeldolgozo|ADR 0010]]).
