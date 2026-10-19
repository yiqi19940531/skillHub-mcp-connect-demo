#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ] || [ ! -f frontend/dist/index.html ]; then
  echo '请先运行 ./scripts/setup.sh 安装依赖并构建前端。' >&2
  exit 1
fi
exec .venv/bin/python -m scripts.serve
