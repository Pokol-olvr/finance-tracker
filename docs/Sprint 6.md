---
projekt: Pénzügyi nyomkövető
sprint: S6
kezdes: 2027-01-11
vege: 2027-01-24
story_pont: 24
tags: [penzugy, sprint]
---

# Sprint 6

Vissza: [[Fejlesztési terv]]

## Sprint cél

**A webapp a Pi-re költözik, telefonról is elérhető, de csak a Tailscale-hálózatról, HTTPS-sel és kétfaktoros belépéssel. A Pi megerősítve, a Pi-hole és az Unbound mellett fut, és a Vaultwarden is rákerül. A továbbított e-mailes számla magától a bronzba kerül. A sprint végén a `finance` adatbázis üresen újraépül, és indul az éles használat.** A sprint 2027-01-11 és 2027-01-24 között tart, 24 story ponttal.

| Kulcs | Jegy | SP | Függ tőle |
| --- | --- | --- | --- |
| FIN-313 | A Pi megerősítése | 3 | – |
| FIN-301 | Tailscale a Pi-n, a telefonokon és az otthoni gépen | 2 | – |
| FIN-315 | Együttélés a Pi-hole-lal és az Unbounddal | 2 | FIN-301 |
| FIN-302 | Caddy HTTPS a saját domainen | 2 | FIN-301, FIN-315 |
| FIN-303 | Authelia TOTP 2FA két felhasználóval | 3 | FIN-302 |
| FIN-308 | Webapp és postaláda költözése a Pi-re | 3 | FIN-301, FIN-302, FIN-303 |
| FIN-314 | Vaultwarden a Pi-n | 3 | FIN-302, FIN-313 |
| FIN-307 | E-mailes számlafogadás | 5 | FIN-312 |
| FIN-309 | A `finance` adatbázis üres újraépítése | 1 | FIN-308, FIN-307 |

Javasolt sorrend: FIN-313, FIN-301, FIN-315, FIN-302, FIN-303, FIN-308, FIN-314, FIN-307, FIN-309. A megerősítés az első, mert a Pi már DNS-szerverként szolgálja ki a háztartást, és minden új szolgáltatás erre épül. A hálózat, a portok, a tanúsítvány és a belépés egymásra épül, a FIN-308 csak ezek után költözteti a webappot. A Vaultwarden a webapp után jön, mert ugyanazt a Caddyt és tanúsítványt használja. A FIN-307 a workerben fut, ezért a Pi-től függetlenül is haladhat, ha a Pi-s rész elakad. A FIN-309 az utolsó, mert utána már csak valódi adat kerül a rendszerbe.

**Előfeltétel:** a `v0.5.0` kiadva és az otthoni stackre telepítve. A Sprint 4 nyitott, saját számlás pontjai (FIN-412, FIN-312) a FIN-307 első valódi számlájával lezárhatók.

**Változás a tervhez képest:** az otthoni stack 2026-11-17-től a Windowsos gépen fut, WSL2-ben, RTX 5070 GPU-val; a Fedorás laptopon a projekten már nem dolgozunk. A WSL nyitott ablak nélkül leáll, ezért a FIN-301 része a WSL indítása a Windows indulásakor és a tükrözött hálózat.

**A Pi jelenlegi szerepe:** natív Pi-hole v6 és Unbound fut rajta, ez a háztartás DNS-szervere; a DHCP-t a router adja, a Pi-hole NTP-szervert is ad. Debian 13-as Raspberry Pi OS fut rajta, a Docker és a Tailscale már fent van, mellettük a Beszel monitorozás. Ami ezt megszakítja, az az internetet is elveszi, ezért minden lépésnek van visszaútja, és a Pi-hole portjai nem változhatnak meg a helyi hálózaton.

**Port forward nincs és nem is lesz:** a Tailscale NAT mögül is kapcsolódik, minden kapcsolatot az otthoni gép nyit, a tanúsítvány DNS-alapú.

**Adat:** a Pi és az e-mail beállításai, a domain, a címek és a titkok csak a `.env`-ekbe kerülnek, a repóba nem. A tesztekhez kitalált levelek és címek kellenek.

## FIN-301 Tailscale a Pi-n, a telefonokon és az otthoni gépen · 2 SP

**Story:** felhasználóként a telefonomról akarom elérni a webappot, hogy ne kelljen a fotót a laptopra áttenni, de kívülről senki ne lássa.

**Részfeladatok**

- [ ] Tailscale a Pi-n, a két telefonon és az otthoni gépen, egy tailnetben 📅 2027-01-24
    - 2026-11-18: a Pi-n és a feldolgozó gépen fut, az egyik telefon a tailnetben van; a második telefon hátravan.
- [ ] ACL: a telefonok csak a Pi webappját és az otthoni gép riportjait érik el, az otthoni gép a Pi-t 📅 2027-01-24
- [x] WSL-es otthoni gépnél: a Tailscale a Windows-oldalon fut; a WSL tükrözött hálózattal (`networkingMode=mirrored`) a Tailscale-címen is látszik, a riportok a `home/docker-compose.tailnet.yml`-lel a `127.0.0.1` mellett a Tailscale-címen is 📅 2027-01-24
- [x] A WSL bejelentkezéskor elindul, és ablak nélkül is fut (`scripts/windows/wsl-autostart.ps1`), így a worker és a timerek nyitott terminál nélkül is dolgoznak 📅 2027-01-24
- [x] A Pi-n nincs nyitott bejövő port a routeren 📅 2027-01-24
- [x] A tükrözött hálózatban a Windows saját Postgrese (5432) ütközött a stackével: a stacké a `POSTGRES_PORT=5433`-ra került 📅 2027-01-24

**Elfogadási feltételek**

- [ ] A webapp csak a Tailscale-hálózatról érhető el
- [ ] Mobilnetről, Tailscale nélkül a Pi címe nem válaszol
- [x] Az otthoni gép a Pi-t a Tailscale-címén éri el
- [x] A riportok a Pi-ről a tailneten elérhetők, a helyi hálózatról Tailscale nélkül nem (2026-11-18)

## FIN-313 A Pi megerősítése · 3 SP

**Story:** a Pi gazdájaként a lehető legkevesebb joggal akarok belépni a mindennapokban, és ki akarom zárni a próbálkozókat, hogy a DNS-szerver és a postaláda ne legyen könnyű célpont.

**Részfeladatok**

- [x] SSH csak kulccsal: `PasswordAuthentication no`, `PermitRootLogin no`, `AllowUsers` a két felhasználóval 📅 2027-01-24
- [x] Korlátozott felhasználó: SSH-val beléphet, de nincs `sudo`, nincs a `docker` csoportban (a `docker` csoport rootjogot ad), és a beállítófájlokat nem írhatja 📅 2027-01-24
- [x] A rendszergazda-felhasználó külön, kulccsal; a `sudo` jelszót kér 📅 2027-01-24
- [x] fail2ban: `sshd` jail, 5 hibás próbálkozás 10 percen belül, 1 órás kitiltás 📅 2027-01-24
- [x] fail2ban jail a Vaultwarden és az Authelia naplójára (a FIN-314-gyel és a FIN-303-mal) 📅 2027-01-24
    - 2026-11-18: `scripts/pi/fail2ban-web.sh`, a Pi Tailscale-je nem címzi át a továbbított forgalmat (`scripts/pi/tailscale-nosnat.sh`).
- [x] Tűzfal (`ufw`): 53 a helyi hálózatról és a tailnetről, 22 a helyi hálózatról és a tailnetről, 80 és 443 a tailnetről és a Pi-hole felületéhez a helyi hálózatról; NTP, mDNS és a Beszel a helyi hálózatról; minden más tiltva. Konzolos visszaút helyett 5 perces önvisszavonó időzítő 📅 2027-01-24
- [x] `unattended-upgrades` a biztonsági frissítésekre, újraindítás nélkül 📅 2027-01-24
- [x] Script a beállításhoz, a README-ben a visszavonás lépéseivel (`scripts/pi/`) 📅 2027-01-24
- [x] Kulcscsere scripttel (`scripts/windows/rotate-ssh-key.ps1`); 2026-11-17-én az `olvaso` kulcsán kipróbálva, a rendszergazdai kulcs jelmondatot kapott 📅 2027-01-24
- [ ] Éves kulcscsere, először 2027-11-17-én 📅 2027-01-24

**Elfogadási feltételek**

- [x] Jelszóval nem lehet SSH-val belépni, roottal sem
- [x] A korlátozott felhasználó belép, de `sudo` és `docker` parancsa elutasítva
- [ ] Öt hibás SSH-próbálkozás után a cím ki van tiltva, és a `fail2ban-client status sshd` mutatja
    - A feldolgozó gép kivétel, a próba a telefonról vagy egy másik gépről kell.
    - 2026-11-17: a laptop kulcs nélküli próbálkozásait a fail2ban nem számolta, mert a Debian 13 az `sshd-session` folyamatban naplóz. Az `aggressive` mód és a szélesebb `journalmatch` után a mai naplóból 28 sort talál; a tiltás próbája még hátravan.
- [x] A tűzfal bekapcsolása után a helyi hálózat DNS-e és az internet tovább működik

**Mérés 2026-11-17:** a tűzfal után a helyi hálózatról működött a DNS, az SSH mindkét felhasználóval, a Pi-hole felülete és a Beszel, a Tailscale közvetlen kapcsolatokkal ment; a tiltott 45876-os port nem válaszolt.

## FIN-315 Együttélés a Pi-hole-lal és az Unbounddal · 2 SP

**Story:** a háztartás internetéért felelősként azt akarom, hogy az új szolgáltatások ne zavarják a Pi-hole-t, és a saját domain csak a tailnetről legyen feloldható.

**Részfeladatok**

- [x] A Pi-hole v6 webszervere (`webserver.port`) csak a helyi hálózati címen figyel, így a Tailscale-cím 80-as és 443-as portja a Caddyé 📅 2027-01-24
- [x] Az Unbound a `127.0.0.1:5335`-ön marad, a Pi-hole továbbra is ezt kérdezi 📅 2027-01-24
- [x] Belső DNS-rekordok a Pi-hole-ban: a pénzügyi név, az `auth.` aldomainje és a Vaultwarden neve a Pi Tailscale-címére 📅 2027-01-24
- [x] Tailscale split DNS: a domain a Pi Tailscale-címén lévő Pi-hole-hoz megy 📅 2027-01-24
- [x] Globális névszerver a tailneten is a Pi-hole, „Override DNS servers” bekapcsolva, így a reklámszűrés otthonon kívül is működik 📅 2027-01-24
- [x] A Cloudflare-ben nincs rekord a belső címre; a Cloudflare csak a tanúsítvány DNS-ellenőrzéséhez kell 📅 2027-01-24
- [x] A Pi maga nem a Tailscale DNS-ét használja (`--accept-dns=false`), így a `tailscaled` kiesése nem viszi el a névfeloldását 📅 2027-01-24
- [ ] A `127.0.0.1` kifejezett névszerverként a NetworkManagerben, egyeztetett időpontban, mert az újracsatlakozás rövid kiesés 📅 2027-01-24

**Elfogadási feltételek**

- [ ] A Pi-hole felülete a helyi hálózatról a megszokott címen elérhető, a Caddy pedig a Tailscale-címen fut
    - A felület 2026-11-17-én a helyi címen elérhető; a Caddy a FIN-302-vel indul.
- [ ] A domain a tailneten a Pi Tailscale-címére oldódik fel, a nyilvános DNS-ben nincs rá rekord
    - 2026-11-17: a Pi-hole a három nevet a Pi Tailscale-címére oldja fel, a nyilvános DNS-ben nincs rekord; a tailneten a split DNS után ellenőrizendő.
- [ ] Leállított Pi-hole mellett a telefonok a tailneten is elérik az internetet
    - Változás 2026-11-17: tudatos döntés, hogy a tailnet globális DNS-e a Pi-hole, a reklámszűrés miatt. A Pi kiesésekor a tailnetes eszközökön nincs névfeloldás; ilyenkor a Tailscale kikapcsolása visszaadja az internetet. A feltétel ezért nem teljesül, és nem is cél.

## FIN-302 Caddy HTTPS a saját domainen · 2 SP

**Story:** felhasználóként érvényes HTTPS-t akarok, hogy a böngésző ne figyelmeztessen, és a PWA a kamerát is elérje.

**Részfeladatok**

- [x] Caddy a `pi/` Compose-ban, a DNS-szolgáltató pluginjával 📅 2027-01-24
- [x] DNS-alapú ACME-ellenőrzés, mert az oldal kívülről nem látszik 📅 2027-01-24
- [x] Belső DNS-rekord a Pi Tailscale-címére a Pi-hole-ban (FIN-315) 📅 2027-01-24
- [x] A DNS API-kulcs csak a Pi `.env`-jében, a lehető legszűkebb joggal 📅 2027-01-24

**Elfogadási feltételek**

- [x] Érvényes tanúsítvány, a böngésző nem figyelmeztet
    - 2026-11-18: Let's Encrypt-tanúsítvány a pénzügyi névre és az `auth.` aldomainre, 2027-02-15-ig; a Cloudflare-token csak a zónára szól, DNS Edit és Zone Read joggal, 2027-11-18-ig.
- [ ] A tanúsítvány megújul emberi beavatkozás nélkül (a Caddy naplója mutatja)
- [x] HTTP-ről HTTPS-re irányít
    - 2026-11-18: `http://` a tailnetről 308-cal a `https://` címre.
- [ ] A Cloudflare-token cseréje 2027-11-18 előtt, az SSH-kulcsok éves cseréjével együtt

## FIN-303 Authelia TOTP 2FA két felhasználóval · 3 SP

**Story:** felhasználóként második faktort akarok a belépéshez, hogy egy elveszett, de a tailnetbe belépett telefon se legyen elég.

**Részfeladatok**

- [x] Authelia a `pi/` Compose-ban, fájlalapú felhasználókkal, a Caddy `forward_auth` mögött 📅 2027-01-24
- [x] Két felhasználó a `HOUSEHOLD_MEMBERS` kódjaival, TOTP-vel 📅 2027-01-24
    - 2026-11-18: felhasználói fájl nélkül az Authelia egy példafelhasználót hozott létre; az Authelia leállítva, a fájl törölve, amíg a két valódi felhasználó nincs fent.
    - 2026-11-18: mindkét felhasználó fent (`scripts/authelia-user.sh`, a fájl `600`, root), az Authelia fut, mindkettőnek SHA1-es TOTP-ja van, a telefon beépített kódgenerátorával.
    - A script elnyelte az Authelia jelszókérdését, ezért a második felhasználónál nem látszott, hogy jelszóra vár; javítva, a kérdés már látszik.
    - A regisztrációhoz kért megerősítő kód után az emelt jogú munkamenet néhány perc alatt lejár; ha addig nincs beírva a TOTP-kód, a regisztráció „rossz kód”-dal hiúsul meg, és elölről kell kezdeni.
- [x] A worker API (`/inbox/…`) Authelia nélkül, csak a `WORKER_API_TOKEN`-nel érhető el 📅 2027-01-24
- [x] A webapp a belépett felhasználót a fejlécből veszi, így a feltöltő nem választható szabadon 📅 2027-01-24
- [x] Munkamenet-idő és kizárás túl sok hibás próbálkozás után 📅 2027-01-24

**Elfogadási feltételek**

- [x] Második faktor nélkül nincs hozzáférés
    - 2026-11-18: belépés nélkül a domain a belépőoldalra irányít (302), a szabály `two_factor`, az alapszabály `deny`.
- [x] A worker token nélkül nem éri el az API-t, tokennel 2FA nélkül is
    - 2026-11-18: `/inbox/items` token nélkül 401, `/health` 200, a webapp portja közvetlenül nem érhető el.
- [x] A feltöltő mindig a belépett felhasználó
    - 2026-11-18: belépés nélkül a kliens által küldött `Remote-User` fejléc is a belépőoldalra irányít; belépve a fejlécet a Caddy az Authelia válaszából írja felül.

## FIN-308 Webapp és postaláda költözése a Pi-re · 3 SP

**Story:** felhasználóként a Pi-re akarom költöztetni a webappot, hogy a feltöltés akkor is működjön, ha az otthoni gép ki van kapcsolva.

**Részfeladatok**

- [x] `pi/docker-compose.yml`: webapp, Caddy, Authelia; az adat a Pi `DATA_DIR`-jében 📅 2027-01-24
- [x] A webapp ARM-képe a Pi-n épül 📅 2027-01-24
    - 2026-11-18: `arm64`, a Pi-n a `docker compose up --build` építi.
- [x] Az otthoni worker `INBOX_URL`-je a Pi Tailscale-címére mutat, minden kapcsolatot az otthoni oldal nyit ([[0006-blokkbeolvasas-a-pi-elott|ADR 0006]]) 📅 2027-01-24
- [x] Az otthoni Compose-ból kikerül a webapp; az állapot képernyő a Pi-n marad, a jelentést az otthoni gép küldi ([[0008-allapot-kepernyo-a-webappban|ADR 0008]]) 📅 2027-01-24
    - A helyi postaláda a `home/docker-compose.inbox.yml` kiegészítésbe került: Pi nélkül, fejlesztéshez és a CI-ban ez az alap (`init-env.sh`), a Pi-vel kimarad. Az `INBOX_URL` kötelező lett.
    - 2026-11-18: az otthoni `.env`-ben az `INBOX_URL` és a `STATUS_URL` a Pi https-címe; a `--remove-orphans` leállította a helyi webappot. A régi `.env` a repón kívül, a WSL-ben megmaradt, a helyi postaláda adatai is.
    - A Pi postaládája üresen indult: a worker a 19 döntésre váró ellenőrző csomagot magától feltöltötte, döntés és szabály még nem volt, így átmásolni nem kellett semmit.
- [x] A Pi postaládája a mentésbe nem kerül, csak átmeneti tároló 📅 2027-01-24
    - A feltöltés a Garage-ba és a bronzba kerül, a döntéseket a worker behúzza; ami a Pi-n marad, az elveszhet. Az Authelia adata (felhasználók, TOTP) sincs mentve: elvesztésekor a felhasználókat újra kell venni, és a TOTP-t újra kell regisztrálni.
- [x] A README telepítési része a Pi-vel 📅 2027-01-24
- [x] A webapp adatbázis nélkül is fut; a kézi bejegyzés API-ja a Pi-n 503, amíg a FIN-606 a kimenő sorra nem viszi 📅 2027-01-24

**Elfogadási feltételek**

- [x] Telefonról feltölthető, a worker a Pi postaládájából húz
- [x] Kikapcsolt otthoni gépnél a feltöltés a Pi-n vár, bekapcsolás után feldolgozódik
    - 2026-11-18: leállított workernél a telefonos feltöltés a Pi-n `new` állapotban várt; a worker indulás után egy percen belül feldolgozta, a tétel `closed`. A worker, a gép és a betétdíj jelentése másodpercekkel frissebb volt a Pi-n.
- [ ] Az Ellenőrzés, a Szabályok és a Betétdíj a Pi-n is működik
    - 2026-11-18: az Ellenőrzés és az állapot képernyő a Pi-n működik. A Szabályok és a Betétdíj oldalán ismert, a költözéstől független hibák vannak, ezekre később, külön jegyben térünk vissza.

## FIN-314 Vaultwarden a Pi-n · 3 SP

**Story:** a háztartás tagjaként a jelszavainkat a saját Pi-nken akarom tartani, a tailnetről elérhetően, hogy ne kelljen felhős jelszókezelő.

**Részfeladatok**

- [x] Vaultwarden a `pi/` Compose-ban, a `vault.` aldomainen a Caddy mögött; az Authelia nem áll elé, mert a Bitwarden-kliensek saját belépést használnak 📅 2027-01-24
    - 2026-11-18: 1.37.5, Let's Encrypt-tanúsítvány a `vault.` névre, a Pi-hole helyi rekordja a FIN-315-ből.
- [x] Regisztráció lezárva; az admin felület alapból kikapcsolva, argon2-es tokennel kapcsolható 📅 2027-01-24
    - 2026-11-18: egy fiók, a második személynek egyelőre nem kell; a regisztráció a fiók létrehozásáig volt nyitva (`VAULT_SIGNUPS_ALLOWED`), utána `disableUserRegistration: true`. Meghívó helyett ez, mert levélküldés nincs. Az admin felület: „The admin panel is disabled”.
- [ ] Kötelező kétfaktoros belépés a fiókra (Authenticator app, a recovery code a mesterjelszó mellett) 📅 2027-01-24
- [x] Napi mentés: az otthoni gép húzza le a Vaultwarden adatát, és a restic-tárolóba teszi; a kapcsolatot itt is az otthoni oldal nyitja 📅 2027-01-24
    - A `mentes` felhasználó kulcsa kényszerített paranccsal csak a friss mentést kapja (`scripts/pi/backup-user.sh`); más parancs, alagút és shell kipróbálva elutasítva. A mentésben az Authelia adata és a `pi/.env` is benne van, mert a TOTP-titkok a benne lévő kulccsal titkosítottak.
    - 2026-11-18: az első `pi` pillanatkép 591 KiB.
- [x] Visszaállítási próba egy eldobható Vaultwardenbe (`scripts/restore-test-pi.sh`) 📅 2027-01-24
    - 2026-11-18: 1 felhasználó, 13 bejegyzés, 2 TOTP, mindkét adatbázis integritása rendben, az eldobható Vaultwarden elindult rajta.
- [x] fail2ban jail a Vaultwarden hibás belépéseire (FIN-313) 📅 2027-01-24
    - `scripts/pi/fail2ban-web.sh`: az Authelia és a Vaultwarden is, a forward ponton, külön láncban az SSH-étól. Rossz jelszavas próbával mindkét szűrő talált.
    - Előfeltétel volt, hogy a Pi Tailscale-je ne címezze át a továbbított forgalmat (`scripts/pi/tailscale-nosnat.sh`): addig minden kérés a Docker-átjáró címéről jött.

**Elfogadási feltételek**

- [ ] A Bitwarden-kliens a telefonról és a gépről, a tailneten át szinkronizál
    - 2026-11-18: a gépen a böngészőbővítmény szinkronizál, a Firefox jelszavai importálva; a telefon hátravan.
- [x] Idegen nem regisztrálhat, és az admin felület token nélkül nem nyílik meg
- [x] Egy napi mentésből a széf visszaállítható
- [x] A Vaultwarden adata a `finance` mentésétől külön pillanatképben van, és a FIN-309 nem törli

## FIN-307 E-mailes számlafogadás · 5 SP

**Story:** felhasználóként a számláimat egy saját domaines postaládába akarom kapni, hogy ami oda érkezik, magától bekerüljön, letöltés és feltöltés nélkül.

**Elképzelés (2026-11-18):** a saját domainen egy cím, pl. `szamla@`, ez postaládaként működik: a boltoknál és szolgáltatóknál a számlacímet erre állítjuk át, és a régi számlák továbbítva is ide jönnek. A worker figyeli, és minden új levelet a bronzba visz: a feladó címével, a tárggyal, a törzzsel és a mellékletekkel (PDF vagy más fájl, amelyben az összeg van). Ha nincs melléklet, a számla a levél törzsében is lehet. Postafiók: mailbox.org vagy Posteo IMAP-pal, a Proton IMAP-ja csak a Bridge-dzsel menne, ezért nem jó. A cím a Cloudflare Email Routinggal továbbít a postafiókba, így szolgáltatóváltáskor a cím marad.

**Nyitott kérdések:** ki a vásárló, ha a bolt közvetlenül küld (javaslat: személyenként egy cím, pl. két alias, vagy az Ellenőrzésen dől el); mi kerül be idegen feladótól (javaslat: érvényes DKIM- vagy SPF-eredménnyel bármelyik feladó, a többi a postafiók „Karantén” mappájába, és minden levél az Ellenőrzésen dől el).

**Részfeladatok**

- [ ] Postafiók a levelezőszolgáltatónál, a saját domaines cím a Cloudflare Email Routinggal 📅 2027-01-24
- [ ] Worker: IMAP-lehúzás titkosított kapcsolaton, a feldolgozott levél a „Feldolgozva” mappába kerül 📅 2027-01-24
- [ ] Feladó-ellenőrzés SPF- és DKIM-eredménnyel; ami nem megy át, a „Karantén” mappába kerül 📅 2027-01-24
- [ ] A bronzba a feladó, a tárgy, a törzs és a mellékletek; a vásárló a címzett címből vagy az Ellenőrzésen; címkék a tárgyból (`#élelmiszer #háztartás`), ha van 📅 2027-01-24
- [ ] A nyers `.eml` és a mellékletek a Garage-ba, a bronzban `email` forrástípussal (migráció) 📅 2027-01-24
- [ ] A PDF-melléklet ugyanazon az úton megy, mint a webes feltöltés ([[0010-pdf-olvasas-es-szamlafeldolgozo|ADR 0010]]) 📅 2027-01-24
- [ ] Kitalált levelekkel tesztek: hamis DKIM, melléklet nélküli levél, számla a törzsben, továbbított levél 📅 2027-01-24

**Elfogadási feltételek**

- [ ] A boltól közvetlenül érkező és a továbbított PDF-számla is bekerül a bronzba, és megjelenik az Ellenőrzésen
- [ ] Hamis vagy ellenőrizetlen feladó levele nem kerül be, és a postafiók „Karantén” mappájában marad
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
- [ ] A Pi-hole frissítése (`pihole -up`): 2026-11-17-én a Core, a Web és az FTL is egy verzióval le van maradva; rövid DNS-kiesés, ezért egyeztetett időpontban 📅 2027-01-24

**A tervezésen eldöntendő**

- [ ] A levelezőszolgáltató és a `szamla@` postafiók; támogatja-e az IMAP-ot és az alkalmazásjelszót 📅 2027-01-11

**Eldöntve a tervezés előtt**

- [x] Az otthoni stack, a feldolgozó, a Windowsos gépen fut WSL2-ben, GPU-val (2026-11-17).
- [x] A postaláda egy Raspberry Pi 4, Raspberry Pi OS 64 bittel; a webapp képe arm64-re épül.
- [x] A HTTPS a saját domainen, Cloudflare DNS-sel; a Caddy a Cloudflare-pluginnal, csak DNS-szerkesztési joggal rendelkező tokennel kéri a tanúsítványt.
- [x] A Pi-n natív Pi-hole v6 és Unbound fut, ez a háztartás DNS-e; a domain belső rekordjai ide kerülnek, a tailneten split DNS-sel.
- [x] A tailnet globális DNS-e is a Pi-hole (Override DNS servers), hogy a reklámszűrés otthonon kívül is működjön; a Pi kiesése így a tailnetes eszközök DNS-ét is viszi (2026-11-17).
- [x] A Vaultwarden is a Pi-re kerül, és a Pi megerősítése (korlátozott felhasználó, fail2ban) ebbe a sprintbe tartozik.
- [x] Tailscale marad, nem Headscale, mert így nincs kívülről elérhető vezérlőszerver ([[0003-tailscale-a-wireguard-helyett|ADR 0003]]).

- [x] Minden kapcsolatot az otthoni oldal nyit, a Pi-re és az otthoni hálózatba nem kell bejövő port ([[0006-blokkbeolvasas-a-pi-elott|ADR 0006]]).
- [x] A Tailscale marad a WireGuard helyett ([[0003-tailscale-a-wireguard-helyett|ADR 0003]]).
- [x] A riportfelület az otthoni stackben marad, a Pi-ről nem kell elérnie a goldot ([[0014-streamlit-a-metabase-helyett|ADR 0014]]).
- [x] Az e-mailes számla PDF-je ugyanazon a feldolgozón megy át, mint a feltöltött ([[0010-pdf-olvasas-es-szamlafeldolgozo|ADR 0010]]).
