#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${CORE_DIR}/.venv"
VENV_PY="${VENV_DIR}/bin/python"

# Keep services/core/scripts focused on the default backend entrypoint.
# Freeze or move one-off rollout/canary tooling elsewhere instead of adding it here.

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
ENABLE_RELOAD="${ENABLE_RELOAD:-0}"

# Prefer Python 3.11+ if available (project requires >=3.11).
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
  else
    PYTHON_BIN="python3"
  fi
fi

if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
then
  echo "[ERROR] Python 3.11+ is required. Current: $("${PYTHON_BIN}" -V 2>&1 || true)"
  echo "[ERROR] Install Python 3.11+ and re-run, or set PYTHON_BIN to a 3.11+ interpreter."
  exit 2
fi

if [[ ! -x "${VENV_PY}" ]]; then
  echo "[INFO] Creating virtual environment at ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

if ! "${VENV_PY}" - <<'PY' >/dev/null 2>&1
import importlib.util
required = ("uvicorn",)
raise SystemExit(0 if all(importlib.util.find_spec(name) is not None for name in required) else 1)
PY
then
  echo "[INFO] Installing backend dependencies into ${VENV_DIR}"
  "${VENV_PY}" -m pip install --upgrade pip >/dev/null
  "${VENV_PY}" -m pip install -e "${CORE_DIR}[dev]"
fi

echo "[INFO] Starting backend with ${VENV_PY}"

UVICORN_ARGS=(--app-dir "${CORE_DIR}" app.main:app --host "${HOST}" --port "${PORT}")
if [[ "${ENABLE_RELOAD}" == "1" ]]; then
  UVICORN_ARGS+=(
    --reload
    --reload-exclude ".mempalace/*"
    --reload-exclude ".venv/*"
    --reload-exclude "*.log"
  )
  echo "[INFO] Dev reload enabled (ENABLE_RELOAD=1)"
fi

exec "${VENV_PY}" -m uvicorn "${UVICORN_ARGS[@]}" "$@"
