#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python -m scripts.seed_demo
echo '准备完成。启动：./scripts/start.sh'
