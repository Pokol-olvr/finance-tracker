# 0003 Tailscale a WireGuard helyett

**Állapot:** elfogadva

**Dátum:** 2026-10-27

## Kontextus

A telefonoknak el kell érniük a Pi-t, az otthoni workernek pedig a Pi-t, miközben blokkok, bérpapírok és tartozások adatai mozognak. Az otthoni hálózatba nem akarunk bejövő portot nyitni.

## Döntés

A már meglévő Tailscale-t használjuk privát hálózatnak, az Authelia 2FA-val együtt. A részletek: [[Technikai terv]].

## Elvetett alternatívák

- **Saját WireGuard:** a kulcsokat és a társakat kézzel kellene kezelni minden eszközön, és legalább egy végpontnak nyitott porttal kellene várnia a kapcsolatot.

## Következmények

- Nem kell portot nyitni, a webapp kívülről nem látszik.
- A Tailscale vezérlőszervere nem nyílt forrású ([forrás](https://github.com/trigram-dev/headscale)). Ha ez gond lesz, a nyílt Headscale futhat a Pi-n, de annak kívülről elérhetőnek kell lennie.
