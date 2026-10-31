# 0004 Rootless Podman a Docker helyett

**Állapot:** elfogadva

**Dátum:** 2026-10-31

## Kontextus

A főgépen, ahol a stack indul, Podman van, Docker nincs. Az 1. sprint tesztjei Podmannel futottak, és a Compose-fájl változtatás nélkül működött. A stacknek folyamatosan futnia kell, és a gép újraindítását is túl kell élnie.

## Döntés

A főgépen rootless Podman futtatja a Compose-fájlokat, a beállítást a `scripts/setup-podman.sh` végzi. A CI GitHub Actionsben Dockerrel fut, ezért a Compose-fájl mindkettőn működjön. A Pi és a Proxmox futtatójáról a beállításukkor döntünk.

## Elvetett alternatívák

- **Docker Engine a főgépre:** plusz rendszerszolgáltatás, root jogú daemonnal, ami a mostani stackhez nem ad semmit.

## Következmények

- Nincs root jogú daemon, a konténerek a felhasználóhoz tartoznak.
- Daemon híján az újraindítás utáni indítást a `podman-restart.service`, a kijelentkezés utáni futást a linger adja.
- A Postgres adatmappája a konténer felhasználójáé, törléséhez `podman unshare` kell.
- Az Ollamához a 4. sprintben külön NVIDIA CDI-beállítás kell, a Compose-zal való együttműködést akkor kell kipróbálni.
