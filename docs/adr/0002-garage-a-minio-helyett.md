# 0002 Garage a MinIO helyett

**Állapot:** elfogadva

**Dátum:** 2026-10-27

## Kontextus

A nyers blokkfotóknak, tanítási adatkészleteknek és modelleknek S3-kompatibilis, saját gépen futó object store kell. A rendszer nyílt forrású eszközökből áll, és a stack később a Proxmoxra költözik.

## Döntés

A [Garage](https://garagehq.deuxfleurs.fr/) egycsomópontos telepítését használjuk (AGPLv3). A részletek: [[Technikai terv]].

## Elvetett alternatívák

- **MinIO:** a közösségi kiadás 2025 októberétől nem kap Docker image-et, 2026-ban a repót archiválták ([forrás](https://itsfoss.com/news/minio-moves-away-from-open-source/)).

## Következmények

- A Garage S3-kompatibilis, így a worker és a mentés szabványos eszközökkel (rclone) éri el, és a költözéskor egy lépésben átszinkronizálható.
- Az első induláskor a layout, a `raw` bucket és a kulcs automatikusan létrejön; a `datasets` és a `models` bucket a FIN-801-ig még hátravan.
