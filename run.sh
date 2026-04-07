#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DOCKER_IMAGE="python:3.13-slim"

find_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      "$candidate" - <<'PY' >/dev/null 2>&1
import sys
ok = (3, 10) <= sys.version_info[:2] <= (3, 13)
raise SystemExit(0 if ok else 1)
PY
      if [ $? -eq 0 ]; then
        return 0
      fi
    fi
  done
  return 1
}

run_in_docker() {
  docker run --rm \
    -v "$PROJECT_DIR:/app" \
    -w /app \
    "$DOCKER_IMAGE" \
    bash -lc '
      set -euo pipefail
      python -m pip install --no-cache-dir --upgrade pip >/dev/null
      python -m pip install --no-cache-dir smartpy-tezos >/dev/null
      export PYTHONPATH=/app
      python contracts/main.py
    '
}

if [ ! -d "$PROJECT_DIR/.venv" ]; then
  "$PROJECT_DIR/create_venv.sh"
fi

if [ -f "$PROJECT_DIR/.venv/.mode" ] && grep -qx "docker-fallback" "$PROJECT_DIR/.venv/.mode"; then
  run_in_docker
  exit 0
fi

if find_python && [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
  . "$PROJECT_DIR/.venv/bin/activate"
  export PYTHONPATH="$PROJECT_DIR"
  python contracts/main.py
  exit 0
fi

if command -v docker >/dev/null 2>&1; then
  run_in_docker
  exit 0
fi

echo "Erreur: impossible d'exécuter SmartPy. Ni environnement local compatible, ni Docker disponible." >&2
exit 1
