#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN=""

find_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      "$candidate" - <<'PY' >/dev/null 2>&1
import sys
ok = (3, 10) <= sys.version_info[:2] <= (3, 13)
raise SystemExit(0 if ok else 1)
PY
      if [ $? -eq 0 ]; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

if PYTHON_BIN="$(find_python)"; then
  if [ ! -d "$PROJECT_DIR/.venv" ]; then
    "$PYTHON_BIN" -m venv "$PROJECT_DIR/.venv"
  fi

  . "$PROJECT_DIR/.venv/bin/activate"
  python -m pip install --upgrade pip
  python -m pip install --upgrade smartpy-tezos
  exit 0
fi

if command -v docker >/dev/null 2>&1; then
  mkdir -p "$PROJECT_DIR/.venv"
  printf '%s\n' "docker-fallback" > "$PROJECT_DIR/.venv/.mode"
  exit 0
fi

echo "Erreur: aucun Python compatible (3.10 à 3.13) n'a été trouvé, et Docker n'est pas installé." >&2
echo "Installe python3.13/python3.12 ou Docker puis relance." >&2
exit 1
