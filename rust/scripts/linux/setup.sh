#!/usr/bin/env bash
set -euo pipefail

if ! command -v apt-get >/dev/null 2>&1; then
    echo "[ERROR] This setup supports Debian/Ubuntu systems with apt-get." >&2
    exit 1
fi

if [[ $(id -u) -eq 0 ]]; then
    SUDO=()
elif command -v sudo >/dev/null 2>&1; then
    SUDO=(sudo)
else
    echo "[ERROR] sudo is required to install system packages." >&2
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$SCRIPT_DIR/resources/assets/fonts" ]]; then
    ROOT="$SCRIPT_DIR"
else
    ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
fi
FONT_SOURCE="$ROOT/assets/fonts"
if [[ ! -d "$FONT_SOURCE" && -d "$ROOT/resources/assets/fonts" ]]; then
    FONT_SOURCE="$ROOT/resources/assets/fonts"
fi
USER_FONT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts"

echo "Installing Rust GUI build libraries, Pandoc, XeLaTeX, and fonts..."
"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y \
    build-essential pkg-config clang libclang-dev libgtk-3-dev \
    libxcb-render0-dev libxcb-shape0-dev libxcb-xfixes0-dev \
    libxkbcommon-dev libssl-dev \
    pandoc texlive-xetex texlive-lang-arabic texlive-fonts-recommended \
    texlive-latex-extra fonts-noto fonts-noto-cjk fonts-noto-color-emoji \
    fonts-symbola fontconfig

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

if [[ -x "$ROOT/pdf-creator-studio" ]]; then
    echo "Dependencies and user fonts are ready. Launch the app with: $ROOT/run.sh"
else
    echo "Dependencies and user fonts are ready. Build with: cargo build --manifest-path rust/Cargo.toml --release"
fi
