#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${CORE_DIR}/.venv"
VENV_PY="${VENV_DIR}/bin/python"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

if [[ ! -x "${VENV_PY}" ]]; then
  echo "[INFO] Creating virtual environment at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

if ! "${VENV_PY}" - <<'PY' >/dev/null 2>&1
import importlib.util
required = ("uvicorn", "mempalace", "chromadb")
raise SystemExit(0 if all(importlib.util.find_spec(name) is not None for name in required) else 1)
PY
then
  echo "[INFO] Installing backend dependencies into ${VENV_DIR}"
  "${VENV_PY}" -m pip install -e "${CORE_DIR}"
fi

echo "[INFO] Starting backend with ${VENV_PY}"
exec "${VENV_PY}" -m uvicorn app.main:app --reload --host "${HOST}" --port "${PORT}" "$@"
