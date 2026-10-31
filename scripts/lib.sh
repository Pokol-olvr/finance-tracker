# A scripts/ mappa közös része; forrásként töltődik be, önállóan nem fut.
#
# COMPOSE: a Compose-parancs, alapból `docker compose`, Docker nélkül `podman compose`
# ENV_FILE: a használt .env, alapból home/.env

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -z ${COMPOSE:-} ]]; then
  # A szervert nézzük, nem a parancsot: a docker-compose csomag behúzhatja a docker CLI-t
  # futó daemon nélkül, a CI futtatóin viszont a Podman is ott van a Docker mellett.
  if docker info >/dev/null 2>&1; then
    COMPOSE="docker compose"
  else
    COMPOSE="podman compose"
  fi
fi
ENV_FILE=${ENV_FILE:-$REPO_ROOT/home/.env}

if [[ ! -f $ENV_FILE ]]; then
  echo "Hiányzik a $ENV_FILE, futtasd a scripts/init-env.sh-t." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# A relatív utak a home/ mappához képest értendők, a Compose-zal egyezően.
cd "$REPO_ROOT/home"
BACKUP_DIR=${BACKUP_DIR:-./backup}
RESTIC_REPO_DIR=${RESTIC_REPO_DIR:-./backup/restic}

compose() {
  # shellcheck disable=SC2086
  $COMPOSE --env-file "$ENV_FILE" "$@"
}

# Az összes adattábla sorszáma `tábla szám` formában, kiírja a megadott szolgáltatás finance adatbázisából.
row_counts() {
  compose exec -T "$1" psql -U postgres -d finance -At -F ' ' -c "
    select format('%I.%I', schemaname, tablename),
           (xpath('/row/c/text()',
                  query_to_xml(format('select count(*) as c from %I.%I', schemaname, tablename),
                               false, true, '')))[1]::text
    from pg_tables
    where schemaname in ('bronze', 'silver', 'gold')
    order by 1"
}
