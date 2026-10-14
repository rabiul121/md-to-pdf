# Native Rust application

This directory contains the Rust desktop app, command-line converter, shared
settings/profile code, and conversion backend. The desktop UI is built with
`eframe`/`egui`; Markdown preview and editing controls are in `src/app.rs` and
`src/editor.rs`. PDF generation continues to call Pandoc and XeLaTeX, because
those engines provide the document readers, LaTeX rendering, and syntax
highlighting used by the existing product.

## Build and run

Install Rust 1.95 or newer with the MSVC toolchain and Visual Studio C++ Build
Tools on Windows. Run the app from a checkout with `rust/scripts/windows/Run.ps1` and the
CLI with `rust/scripts/windows/Cli.ps1`. On Debian/Ubuntu, install dependencies
with `bash rust/scripts/linux/setup.sh` and install Rust 1.95 or newer,
then launch the app with
`bash rust/scripts/linux/run.sh` or the CLI with
`bash rust/scripts/linux/cli.sh`. To build directly from the repository root:

```powershell
cargo run --manifest-path rust/Cargo.toml --release
cargo run --manifest-path rust/Cargo.toml --release --bin pdf-creator-studio-cli -- --help
```

The app also needs Pandoc and XeLaTeX at runtime. LibreOffice is needed for
legacy `.doc` input; Calibre's `ebook-convert` is needed for `.mobi` input.
`scripts/windows/setup.ps1` installs/checks Pandoc and MiKTeX for the Rust
application and deliberately does not install Python.

The app's built-in Help content is maintained in `docs/USER_GUIDE.md` and is
packaged beside the executable.

For a Windows installer, run
`rust/scripts/windows/Build-Installer.ps1`. The installer build compiles the
Rust desktop binary and stages fonts, the Pandoc template, Lua filter, and user
guide beside it. The installer still uses the repository's Windows bootstrap
and PowerShell installer infrastructure.

On a Debian/Ubuntu build host, run
`bash rust/scripts/linux/Build-Tarball.sh` to create a `.tar.gz` distribution
containing both Rust binaries and the required project resources. Pandoc,
XeLaTeX, fonts, and GUI libraries are installed by the package's `setup.sh`.

## Migration status

This branch contains the Rust implementation; the `main` branch retains the
Python/Flet app. The Rust desktop and CLI release targets have been built on
Windows. Full feature and PDF output parity still needs review. See
[`MIGRATION_STATUS.md`](MIGRATION_STATUS.md) for coverage and remaining work.
