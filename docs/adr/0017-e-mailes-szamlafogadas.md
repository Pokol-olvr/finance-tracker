# 0017 E-mailes számlafogadás saját domaines postafiókkal

**Állapot:** elfogadva

**Dátum:** 2026-11-25

## Kontextus

A számlák egy része csak e-mailben jön, PDF-mellékletként vagy a levél törzsében. A cél, hogy egy saját domaines postafiókba érkező számla letöltés és feltöltés nélkül bekerüljön, ugyanúgy, mint a webes feltöltés. A boltok közvetlenül is küldhetnek a címre, és a régi számlák továbbítva is ide jönnek. A Technikai terv eredetileg csak a két saját címről továbbított levelet engedte volna be, a vásárló pedig a továbbító lett volna; a közvetlenül küldő bolt így kimaradt volna.

Saját levelezőszerver a Pi-n nem jöhet szóba: a levél fogadásához a 25-ös portot kellene megnyitni, porttovábbítás pedig nincs, és az otthoni címről küldött levelet a nagy szolgáltatók spamnek veszik.

## Döntés

- **Postafiók:** a domain MX-rekordja közvetlenül egy EU-s levelezőszolgáltatóra mutat (2026-11-25-től a mailbox.org), a cím pl. `szamla@`. Az SPF, a DKIM és a DMARC a saját domainre is be van állítva.
- **Lehúzás:** a worker IMAP-pal, TLS-en olvassa a postafiókot, egy csak IMAP-ra szóló alkalmazásjelszóval; a kapcsolatot itt is az otthoni gép nyitja. Alapból ötpercenként (`MAIL_POLL_SECONDS`).
- **Feladó-ellenőrzés:** a fogadó szerver `Authentication-Results` fejléce dönt, a levél tetején lévő (vagy a `MAIL_AUTHSERV_ID`-vel megadott szerveré). Bekerül, ha a DMARC `pass`; DMARC-eredmény nélkül akkor is, ha a DKIM- vagy az SPF-eredmény `pass`, és a domainje a feladó domainjére illeszkedik. Ami nem megy át, a postafiók „Karantén” mappájába kerül, és nem kerül a bronzba.
- **Bármely hitelesített feladó:** a bolt közvetlen levele is bekerül; hogy kiadás-e, az Ellenőrzésen dől el, ahogy a feltöltésnél.
- **Vásárló:** ha a feladó egy saját cím (`MAIL_BUYERS`, pl. továbbításnál), a vásárló az ő kódja; a bolt közvetlen levelénél üres.
- **Bronz:** a nyers levél (`.eml`) a Garage-ba, a fejlécadatai a `bronze.email_message` táblába kerülnek. A PDF- és képmellékletek dokumentumként a `bronze.raw_document`-be, `email` forrástípussal; a típust a tartalom dönti el, nem a fájlnév. A beágyazott és a kis kép (logó, aláírás) kimarad, mert a modell feleslegesen olvasná.
- **Számla a törzsben:** melléklet nélkül a levél szövege (HTML-ből sorokra bontva) szöveges dokumentum lesz, modell nélkül, ugyanazzal a feldolgozóval ([ADR 0010](0010-pdf-olvasas-es-szamlafeldolgozo.md)). Az Ellenőrzésen szövegként látszik.
- **Mappák:** a feldolgozott levél a „Feldolgozva” mappába kerül; a worker nem töröl. Ugyanaz a levél a hash-e alapján csak egyszer kerül be.

## Elvetett alternatívák

- **Cloudflare Email Routing továbbítással:** a továbbítás után az SPF-eredmény a Cloudflare-re vonatkozik, nem a feladóra, és a számlák egy harmadik félen is átmennének. A szolgáltatóváltáshoz ott is csak egy rekordot kellene átírni, mint itt.
- **Proton Mail:** IMAP csak az állandóan futó Bridge-dzsel, ami egy újabb szolgáltatás a gépen.
- **Csak a saját címekről:** a közvetlenül küldő bolt kimaradna, és minden számlát kézzel kellene továbbítani.
- **Feladólista boltonként:** a bolt címe változhat, és az Ellenőrzés amúgy is minden dokumentumot elénk tesz.

## Következmények

- A postafiók jelszava csak a `home/.env`-ben van; elvesztésekor az alkalmazásjelszó egy kattintással visszavonható.
- A boltnak a saját domainjére érvényes DKIM- vagy SPF-beállítás kell; aki ezt nem állította be, annak a levele a Karanténba kerül, onnan kézzel továbbítható.
- A csak letöltési linket tartalmazó értesítő továbbra sem dolgozódik fel: a törzse szöveges dokumentum lesz, amelyet az Ellenőrzésen el lehet vetni.
