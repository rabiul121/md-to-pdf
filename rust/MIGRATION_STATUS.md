# Rust migration status

Updated: 2026-10-14

## Current structure

- `src/main.rs`, `src/app.rs`: native desktop UI, editor, Markdown preview,
  conversion status/log, document selection, settings, profiles, help, and
  in-session watch mode.
- `src/editor.rs`: selection-aware Markdown edits and bounded undo/redo.
- `src/config.rs`, `src/profiles.rs`: settings, defaults, built-in and saved
  profiles, app data and output paths. Packaged app data uses platform-native
  user-data locations (including XDG on Linux and Application Support on macOS).
- `src/converter.rs`: shared Pandoc/XeLaTeX invocation, PDF layout/font
  variables, remote image localization, `.doc`/`.mobi` adapters, output naming,
  and conversion diagnostics.
- `src/cli_main.rs`: CLI conversion, configurable watch interval, and interactive wizard with
  input-folder selection, convert-all, and custom-path entry.
- `docs/USER_GUIDE.md`: Rust-specific built-in and packaged help content.
- `scripts/windows/Build-Installer.ps1`: Rust release build and Windows package
  staging.
- `scripts/windows/setup.ps1`: Rust app's Pandoc and MiKTeX runtime setup.
- `scripts/windows/Run.ps1`, `scripts/windows/Cli.ps1`, and
  `scripts/linux/{run,cli}.sh`: Rust source launchers for the GUI and CLI.
- `scripts/linux/setup.sh`: Rust app's Pandoc, XeLaTeX, and bundled-font setup
  for Debian/Ubuntu.
- `scripts/linux/Build-Tarball.sh`: Linux tarball builder for the desktop app,
  CLI, and resources.
- `.github/workflows/rust-build.yml`: Windows installer and Ubuntu Linux
  tarball build gate, including both Rust binaries.
- Both platform packages include the source `input/` folder when present; the
  wizard also accepts custom paths when no packaged inputs are available.

## Parity checklist

| Area | Source implementation | Status |
| --- | --- | --- |
| Native desktop UI with System/Light/Dark themes | egui app | Implemented; build/runtime unverified |
| Markdown editor, formatting toolbar, undo/redo, resizable preview, unsaved-change prompts | `app.rs`, `editor.rs` | Implemented; interaction unverified |
| Batch input, output options, conversion log | `app.rs`, `converter.rs` | Implemented; conversion unverified |
| Page size, margins, typography, TOC and numbering | `config.rs`, `app.rs`, `converter.rs` | Implemented; output parity unverified |
| Profiles and last-used settings | `profiles.rs` | Implemented, including merging partial legacy profile overrides over the selected preset; runtime migration compatibility unverified |
| Built-in help topics and searchable guide | `docs/USER_GUIDE.md`, `app.rs` | Expanded to cover the Python app's main help areas, adapted to the Rust interface; rendering/search unverified |
| Remote images, multilingual fonts, and Windows bundled symbol fonts | `converter.rs` | Implemented; behavior/platform coverage unverified |
| DOC, DOCX, EPUB, MOBI, Markdown, and text inputs | `converter.rs` | Implemented through Pandoc/adapters; unverified |
| CLI (including no-argument interactive wizard) and watch mode with initial and change-triggered conversions | `cli_main.rs`, `app.rs` | Implemented; CLI parity and lifecycle unverified |
| Windows installer and CLI package | Rust GUI/CLI binaries plus existing C#/PowerShell bootstrap | Draft only; installer not built |
| Linux setup, app/CLI launch, and tarball packaging | Rust-specific setup, launchers, and tarball script | Draft only; package not built |
| Remove Python/Flet source and dependencies | Existing app remains in repository | Not done; defer until Rust parity is verified |

## Verification still required

This machine did not have `cargo`, `rustc`, or `rustfmt`, and the approved
environment rejected the Rust toolchain installation attempt. Therefore the
Rust project has not been compiled, formatted by rustfmt, launched, or used to
produce a PDF. The new CI workflow is present but has not run; use its Windows
and Ubuntu build results to fix compiler diagnostics, then compare representative
Markdown and multilingual PDF outputs with the established app. After that,
verify Windows installer install/uninstall and Linux setup before switching the
default launchers or removing the Python implementation.
