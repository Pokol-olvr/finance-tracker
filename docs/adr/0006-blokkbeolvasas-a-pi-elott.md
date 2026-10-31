# 0006 Blokkbeolvasás a Pi előtt, GLM-OCR a laptopon

**Állapot:** elfogadva

**Dátum:** 2026-10-31

## Kontextus

Az eredeti sorrend a Pi postaládával folytatta a 2. sprint után. Egyelőre minden helyben fut, csak mock adattal, a projekt legnagyobb bizonytalansága pedig a blokkbeolvasás. A Pi főleg a telefonos elérés miatt kell. A stack valójában a laptopon fut, amelyben nincs külön GPU, nem a tervekben főgépnek nevezett gépen; a korábbi dokumentumok ezt nem különböztették meg.

## Döntés

A 3–5. sprint a blokkbeolvasást viszi, a Pi és az e-mail a 6. sprintbe kerül. Az első éles használat dátuma marad 2027-01-24. A postaláda API a 3. sprintben készül el, a laptopon futtatva, így a worker a költözéskor csak címet vált.

A modell egyelőre a laptop CPU-ján fut. Az alapmodell a `glm-ocr`, a tartalék a `qwen3-vl:4b`, a finomhangolás pedig csak akkor kell, ha a FIN-407 mérése szerint az alapmodell a saját blokkokon nem elég jó. A részletek: [[Fejlesztési terv]] és [[Sprint 3]].

## Elvetett alternatívák

- **Eredeti sorrend:** a Tailscale, a Caddy és az Authelia most nem ad használható funkciót, a blokkbeolvasás bizonytalansága pedig csak a tervezett 6. sprintben derülne ki.
- **Modell a főgépen:** gyorsabb lenne, de a fejlesztéshez két gépnek kellene futnia.
- **Qwen3-VL alapmodellként:** kitalált blokkon a 4B-s változat 56, a 8B-s 92 másodperc alatt futott, a szóközös ezres tagolást mindkettő elrontotta, és a gondolkodást csak trükkel lehet megkerülni. A GLM-OCR ugyanitt kb. 17 másodperc alatt helyesen olvasta az árakat.

## Következmények

- Egy blokk feldolgozása CPU-n kb. 20 másodperc, a worker sorban, egyszerre egy tétellel dolgozik.
- A GLM-OCR leírásában nem szerepel a magyar, és a mérés számítógéppel rajzolt blokkokon készült. A döntést a FIN-407 saját blokkos mérése igazolja vagy váltja le.
- A telefonos feltöltés csak a FIN-308 után működik, addig böngészőből lehet feltölteni.
- A sprintek összpontszáma 158 SP lett, a Pi-re költözés (FIN-308) és az élesítés előtti újraépítés (FIN-309) új jegyként került be.
- Ha a laptop nem fut, a feldolgozás is áll; a postaláda megőrzi a feltöltéseket.
