#!/usr/bin/env bash
set -euo pipefail

if ! command -v apt-get >/dev/null 2>&1; then
    echo "[ERROR] This installer supports Debian/Ubuntu systems with apt-get." >&2
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
FONT_SOURCE="$REPO_ROOT/assets/fonts"
USER_FONT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts"

if [[ $(id -u) -eq 0 ]]; then
    SUDO=()
elif command -v sudo >/dev/null 2>&1; then
    SUDO=(sudo)
else
    echo "[ERROR] sudo is required to install system packages." >&2
    exit 1
fi

echo "Installing Pandoc, XeLaTeX, Python, and font dependencies..."
"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y \
    pandoc \
    texlive-xetex \
    texlive-lang-arabic \
    texlive-fonts-recommended \
    texlive-latex-extra \
    fonts-noto \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-symbola \
    python3 \
    python3-tk \
    fontconfig

if [[ ! -d "$FONT_SOURCE" ]]; then
    echo "[ERROR] Bundled fonts directory not found: $FONT_SOURCE" >&2
    exit 1
fi

mkdir -p "$USER_FONT_DIR"
find "$FONT_SOURCE" -type f \
    \( -iname '*.ttf' -o -iname '*.otf' -o -iname '*.ttc' \) \
    ! -iname 'seguiemj.ttf' ! -iname 'seguisym.ttf' \
    -exec cp -f {} "$USER_FONT_DIR/" \;
fc-cache -f "$USER_FONT_DIR"

echo "Setup complete. Start the app with bash run.sh or bash launchers/start.sh --cli."
