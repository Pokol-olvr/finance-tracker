# 0008 Állapot képernyő a webappban

**Állapot:** elfogadva

**Dátum:** 2026-10-31

## Kontextus

A feltöltés után semmi nem mutatja, fut-e a modell, hol tart a feldolgozás, és egészséges-e a stack. Eddig ehhez parancsokat kellett futtatni. A kérdések részben általánosak (fut-e a szolgáltatás), részben a saját folyamatunkhoz tartoznak (melyik lépésnél tart a blokk, hány vár még). A workernek nincs healthcheckje, ezért a `compose ps` nem mond róla semmit.

A webapp a FIN-308-cal a Pi-re költözik, az otthoni stack viszont marad. A rendszer szabálya, hogy minden kapcsolatot az otthoni oldal nyit.

## Döntés

Az állapot a webapp `/status` oldalán, saját weboldalként készül, új konténer nélkül. Az adatot két jelentő küldi a webappnak: a gazdagépen egy systemd timer (`scripts/status-report.sh`) és a worker. Mindkettő a meglévő `WORKER_API_TOKEN` tokent használja. A webapp forrásonként csak a legutóbbi jelentést tartja meg. A részletek: [[Sprint 3]].

## Elvetett alternatívák

- **Grafana, Prometheus és cAdvisor:** három új konténer egy egyoldalas kérdésre, és a saját folyamat lépéseit így is nekünk kellene kiírni. A rootless Podman támogatására nem találtunk leírást a cAdvisorhoz, a Podman API-val pedig van [nyitott hibajegye](https://github.com/google/cadvisor/issues/3781). Előzményes grafikon most nem kell.
- **Uptime Kuma:** kész, MIT licencű megoldás HTTP- és TCP-ellenőrzésekkel és státuszoldallal ([forrás](https://www.bitdoze.com/uptime-kuma-vs-gatus/)). A fent-lent állapotot tudja, a blokk lépéseit, a sort és a dbt-futásokat nem.
- **Dozzle:** kényelmes élő naplónézegető ([forrás](https://hub.docker.com/r/amir20/dozzle)), de a Podman-socket kell hozzá, és állapotot nem mutat.
- **Metabase dashboard:** csak a goldot látja, és ha a Postgres leáll, éppen akkor nem mutat semmit.
- **A webapp kérdezi le a szolgáltatásokat:** most működne, de a Pi-ről nem érné el az otthoni stacket.
- **Podman-socket a konténerben:** a socket az összes konténer feletti teljes irányítást adna egy hálózatra nyitott szolgáltatásnak.
- **Külön webszerver az állapotnak:** a webapp leállását is mutatná, de ez a böngészőben amúgy is azonnal látszik, és egy második szolgáltatást kellene a belépés mögé tenni.

## Következmények

- A saját kódot nekünk kell karbantartani, de nincs új konténer és új adatbázis.
- A bővítés egyszerű: új kártyához új mező kell a jelentésbe.
- Ha a webapp nem fut, az oldal sem nyílik meg. Ekkor a `podman compose ps` marad.
- Nincs riasztás és előzmény: a hibát csak az látja, aki megnyitja az oldalt. Éles használat után ezt újra kell nézni.
- Az elavult jelentés szürke, ezért a Pi-re költözés után a kikapcsolt otthoni gép is egyértelműen látszik.
