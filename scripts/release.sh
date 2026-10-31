#!/usr/bin/env bash
# A kiadás lépései, a folyamat leírása: docs/Release folyamat.md
#
#   scripts/release.sh prepare 0.1.0   release ág, a Kiadatlan rész verzióvá alakítása
#   scripts/release.sh tag 0.1.0       címke a main ágon, ez indítja a GitHub Release-t
#   scripts/release.sh notes 0.1.0     egy kiadás szövege a kimenetre
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

changelog="docs/Változásnapló.md"

usage() {
  sed -n '4,6p' "$0" | sed 's/^# *//' >&2
  exit 2
}

fail() {
  echo "$1" >&2
  exit 1
}

[[ $# -eq 2 ]] || usage
command=$1
version=${2#v}
tag=v$version

[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "Érvénytelen verzió: $2 (pl. 0.1.0)"

# A megadott szintű címsor utáni rész a következő kiadásig, üres sorok nélkül a szélein.
section() {
  awk -v heading="$1" '
    found && /^## / { exit }
    found { print }
    index($0, heading) == 1 { found = 1 }
  ' "$changelog" | sed -e '/./,$!d' -e ':a' -e '/^\n*$/{$d;N;ba' -e '}'
}

require_clean_main() {
  [[ $(git branch --show-current) == main ]] || fail "A művelet csak a main ágon futhat."
  [[ -z $(git status --porcelain) ]] || fail "A munkakönyvtár nem tiszta."
  git fetch -q origin
  [[ $(git rev-parse main) == $(git rev-parse origin/main) ]] ||
    fail "A helyi main eltér az origin/main ágtól, előbb frissíts."
}

require_new_tag() {
  if git rev-parse -q --verify "refs/tags/$tag" >/dev/null ||
    git ls-remote --exit-code --tags origin "$tag" >/dev/null; then
    fail "A $tag címke már létezik."
  fi
}

case $command in
  prepare)
    require_clean_main
    require_new_tag
    grep -q '^- ' <<<"$(section '## Kiadatlan')" || fail "A Kiadatlan rész üres, nincs mit kiadni."

    today=$(TZ=Europe/Budapest date +%F)
    git switch -q -c "release/$tag"
    sed -i \
      -e "s/^datum: .*/datum: $today/" \
      -e "s/^## Kiadatlan\$/## Kiadatlan\n\n## $tag · $today/" \
      "$changelog"

    echo "Kész a release/$tag ág. Nézd át a $changelog fájlt, majd commit, push és pull request."
    ;;
  tag)
    require_clean_main
    require_new_tag
    [[ -n $(section "## $tag ·") ]] || fail "A $changelog fájlban nincs $tag rész."

    git tag -a "$tag" -m "$tag"
    git push -q origin "$tag"
    echo "A $tag címke fent van, a GitHub Release a Release workflow-ból készül el."
    ;;
  notes)
    notes=$(section "## $tag ·")
    [[ -n $notes ]] || fail "A $changelog fájlban nincs $tag rész."
    echo "$notes"
    ;;
  *)
    usage
    ;;
esac
