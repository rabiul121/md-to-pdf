#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUST_ROOT="$ROOT/rust"
BUILD_ROOT="$ROOT/build/rust-linux"
PACKAGE_DIR="$BUILD_ROOT/package"
VERSION="$(awk -F'"' '/^version = / { print $2; exit }' "$RUST_ROOT/Cargo.toml")"
ARCH="$(uname -m)"
ARCHIVE="$ROOT/dist/PdfCreatorStudio-Linux-$ARCH-$VERSION.tar.gz"

mkdir -p "$ROOT/build"
ROOT_REAL="$(cd -- "$ROOT" && pwd -P)"
BUILD_PARENT_REAL="$(cd -- "$ROOT/build" && pwd -P)"
case "$BUILD_PARENT_REAL/" in
    "$ROOT_REAL/build/"*) ;;
    *) echo "[ERROR] Refusing to create build files outside the repository build directory." >&2; exit 1 ;;
esac
BUILD_ROOT="$BUILD_PARENT_REAL/rust-linux"
PACKAGE_DIR="$BUILD_ROOT/package"
if [[ -z "$VERSION" ]]; then
    echo "[ERROR] Could not read the Rust app version." >&2
    exit 1
fi

echo "Building the native Rust desktop application..."
cargo build --manifest-path "$RUST_ROOT/Cargo.toml" --release

rm -rf -- "$BUILD_ROOT"
mkdir -p "$PACKAGE_DIR/resources/assets" "$PACKAGE_DIR/resources/src" "$PACKAGE_DIR/resources/docs" "$PACKAGE_DIR/input" "$ROOT/dist"
install -m 755 "$RUST_ROOT/target/release/pdf-creator-studio" "$PACKAGE_DIR/pdf-creator-studio"
install -m 755 "$RUST_ROOT/target/release/pdf-creator-studio-cli" "$PACKAGE_DIR/pdf-creator-studio-cli"
cp -a "$ROOT/assets/." "$PACKAGE_DIR/resources/assets/"
if [[ -d "$ROOT/input" ]]; then cp -a "$ROOT/input/." "$PACKAGE_DIR/input/"; fi
cp "$ROOT/src/template.tex" "$PACKAGE_DIR/resources/src/template.tex"
cp "$ROOT/src/font_filter.lua" "$PACKAGE_DIR/resources/src/font_filter.lua"
cp "$RUST_ROOT/docs/USER_GUIDE.md" "$PACKAGE_DIR/resources/docs/USER_GUIDE.md"
cp "$ROOT/LICENSE" "$PACKAGE_DIR/LICENSE"
cp "$RUST_ROOT/scripts/linux/setup.sh" "$PACKAGE_DIR/setup.sh"

cat > "$PACKAGE_DIR/run.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/pdf-creator-studio" "$@"
EOF
cat > "$PACKAGE_DIR/cli.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/pdf-creator-studio-cli" "$@"
EOF
cat > "$PACKAGE_DIR/README.txt" <<EOF
PDF Creator Studio $VERSION for Linux ($ARCH)

1. Run ./setup.sh once to install Pandoc, XeLaTeX, GUI libraries, and bundled fonts.
2. Run ./run.sh to start the desktop app.
3. Run ./cli.sh --help for command-line usage.

The setup script supports Debian and Ubuntu systems with apt-get.
EOF
chmod 755 "$PACKAGE_DIR/run.sh" "$PACKAGE_DIR/cli.sh" "$PACKAGE_DIR/setup.sh"
tar -C "$BUILD_ROOT" -czf "$ARCHIVE" package
echo "Linux distribution created: $ARCHIVE"
