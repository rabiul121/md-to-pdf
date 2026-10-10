#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON=""
if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
fi
if [[ -z "$PYTHON" ]]; then
    echo "Python 3 is required. Install Python 3, then run this launcher again." >&2
    exit 1
fi
exec "$PYTHON" "$ROOT/main.py" "$@"
