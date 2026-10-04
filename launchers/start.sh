#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$(command -v python3 || true)"
if [[ -z "$PYTHON" ]]; then
    echo "Python 3 is required. Install Python 3, then run this launcher again." >&2
    exit 1
fi
exec "$PYTHON" "$ROOT/main.py" "$@"
