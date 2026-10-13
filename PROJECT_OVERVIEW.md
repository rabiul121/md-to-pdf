# PDF Creator Studio: Project Overview

This document is the handoff brief for future maintainers and AI coding assistants. Read it together with `AGENTS.md` if one is later added, `README.md`, and `docs/USER_GUIDE.md`. Treat the source code as authoritative when behavior differs from this description.

## Purpose

PDF Creator Studio converts Markdown, plain text, DOCX, legacy DOC, EPUB, and MOBI documents into PDFs. It is a desktop application for Windows and Linux/WSL, with a Flet/Flutter graphical interface and an interactive command-line workflow. Its main differentiators are multilingual text handling (English, Bengali, and Arabic), broad typography and page-layout controls, and a Pandoc/XeLaTeX conversion pipeline.

The program does not implement a Markdown or PDF engine itself. Pandoc parses and transforms documents; XeLaTeX lays out and produces PDFs. LibreOffice is needed only for legacy `.doc` inputs, and Calibre's `ebook-convert` is needed only for `.mobi` inputs. DOCX, EPUB, Markdown, and text are handled through Pandoc.

## Main user flows

- **Editor:** Write, paste, open, and save Markdown or plain text; apply Markdown formatting with toolbar actions; optionally inspect a live Markdown preview; export the current buffer to PDF.
- **Documents:** Select one or multiple source files, choose output location and options, convert, then open the generated PDF or output folder.
- **Preferences:** Configure page size, orientation, margins, fonts, spacing, headings, table of contents, page numbers, borders, hyphenation, and saved profiles.
- **Watch mode:** Monitor one selected file and convert it after changes.
- **Help:** Search built-in Markdown help and read the user guide.
- **CLI:** Use the interactive conversion wizard or the platform scripts for one-shot and watch conversion.

## Architecture and important files

| Path | Responsibility |
| --- | --- |
| `main.py`, `__main__.py` | Application entry points and CLI/GUI dispatch. |
| `src/ui/flet_app.py` | Primary Flet interface, view state, event handlers, settings collection, and UI-to-converter calls. |
| `src/ui/legacy_tkinter.py` | Optional older Tkinter interface. Keep it working when changing shared conversion behavior. |
| `src/converter.py` | Legacy/CLI-oriented conversion implementation and command-line flow. Some engine logic is duplicated here; mirror relevant converter fixes or plan a consolidation carefully. |
| `src/core/engine.py` | Conversion engine used by the modern Flet UI. Builds the Pandoc command, selects fonts and template variables, runs Pandoc/XeLaTeX, and reports progress/errors. |
| `src/core/constants.py` | Shared paths, supported extensions, page/font choices, defaults, and font inventory. |
| `src/core/profiles.py` | Profile load/save/update/delete and last-used settings persistence. |
| `src/core/editor.py` | Pure text-buffer transforms used by the Markdown toolbar. |
| `src/core/markdown_preview.py` | Flet Markdown preview styling plus footnote normalization. |
| `src/core/images.py` | Pandoc JSON traversal and optional remote-image download/localization. |
| `src/core/help_topics.py` | Searchable built-in help content. |
| `src/template.tex` | Pandoc LaTeX template. Keep syntax-highlighting macros compatible with Pandoc's `$highlighting-macros$`; fallback commands belong only in the no-highlighting branch to avoid duplicate LaTeX definitions. |
| `src/font_filter.lua` | Pandoc Lua filter for script-aware font selection and specialized symbols/emoji. |
| `assets/fonts/` | Bundled font files organized by script/role. Observe each font's license before redistributing it. |
| `scripts/windows/` | Windows developer setup, CLI wrappers, and installer. |
| `scripts/linux/` | Debian/Ubuntu/WSL setup and CLI wrappers. |
| `launchers/` | Shared launch helpers. |
| `docs/USER_GUIDE.md` | User-facing instructions. |
| `tests/` | Unit and regression coverage for the editor, preview, converter, and UI structure. |
| `profiles.json` | Local development profile data; intentionally ignored by Git. Packaged builds store profiles in `%LOCALAPPDATA%`. |

### Conversion flow

1. The UI or CLI gathers settings and chooses the source document.
2. Legacy DOC and MOBI are converted to an intermediate format when their adapters exist.
3. Remote Markdown images are parsed through Pandoc's JSON reader and downloaded when possible; a failed optional image download is logged and that image is omitted.
4. The engine builds a Pandoc-to-PDF command using `src/template.tex`, `src/font_filter.lua`, and the selected syntax-highlighting style.
5. Pandoc invokes XeLaTeX. Standard error is sent to the conversion log, and successful output is saved under the configured output directory.

The modern UI calls `src.core.engine`; fixes in this path should be mirrored in `src.converter` when the legacy GUI or CLI uses the same affected behavior.

## Development setup

- Python 3.9 or newer is declared in `pyproject.toml`.
- Install Python requirements with `python -m pip install -r requirements.txt`.
- Install Pandoc and XeLaTeX (MiKTeX on Windows; TeX Live's XeLaTeX on Debian/Ubuntu/WSL) using the platform setup scripts or system packages.
- Optional adapters: LibreOffice for `.doc`; Calibre for `.mobi`.
- Windows GUI launch: `run.bat` or `python main.py`.
- Linux launch: `bash run.sh` or `python main.py`.
- The interactive CLI is available from `python main.py --cli` or `scripts/windows/cli_convert.bat` / `scripts/linux/cli_convert.sh`.

## Packaging and installation

The Windows installer build script is `scripts/windows/installer/Build-Installer.ps1`. It uses Flet's PyInstaller integration to package the application and bundled resources, then compiles a small .NET Framework bootstrapper. The per-user installer extracts to `%LOCALAPPDATA%\Programs\PDF Creator Studio`, invokes `scripts/windows/setup.ps1 -PackagedApp` to install Pandoc and MiKTeX if needed, creates Start menu and desktop shortcuts, and registers an uninstaller. Profiles and generated PDFs are stored outside the application install directory and are retained on uninstall.

Building the setup executable requires a Windows host, a working project virtual environment with Flet (and PyInstaller available to Flet), and the .NET Framework C# compiler. Distribution requires users to have network access for missing external prerequisites. Windows may display SmartScreen warnings until the executable is code-signed and has established reputation.

## Data and paths

- Development profiles: repository-root `profiles.json` (ignored; user-specific).
- Packaged profiles/settings: `%LOCALAPPDATA%\PDF Creator Studio`.
- Development PDFs: `output/` (generated PDFs ignored by Git).
- Packaged PDFs: `Documents\Markdown to PDF`.
- Temporary editor buffers: the operating system temporary directory.
- Input samples in `input/` are source examples; do not delete or overwrite user documents as part of cleanup.

## Guidance for AI-assisted changes

1. Inspect the current implementation and `git status` first. Preserve any uncommitted user work.
2. Keep conversion-engine changes consistent between `src/core/engine.py` and `src/converter.py` unless deliberately removing duplication.
3. Preserve the existing supported input formats and keep Markdown and Plain Text modes distinct. Plain Text must not interpret Markdown syntax.
4. When editing the LaTeX template, check the generated Pandoc template semantics. Pandoc-provided highlighting macros must not be shadowed by unconditional `\newcommand` declarations.
5. Keep the Flet UI responsive: expensive conversions run off the event loop, and user-visible errors belong in the conversion log.
6. Keep settings/profile compatibility in mind; prefer additive migrations and preserve user-created profiles.
7. Do not remove fonts, input documents, output PDFs, profile data, release assets, or installer prerequisites as generic cleanup.
8. Update `docs/USER_GUIDE.md` for user-facing behavior and this overview for architecture/build changes.
9. Check tests relevant to the changed feature. Do not update tests merely to make a broken behavior appear correct.
10. For releases, keep `pyproject.toml`, installer metadata, documentation, Git tag, and release notes on the same version.

## Known maintenance opportunities

- `src/core/engine.py` and `src/converter.py` contain overlapping conversion code and can drift.
- The Windows installer depends on externally installed Pandoc and MiKTeX; their first-run setup and update behavior should be checked on a clean Windows account.
- Packaged-app and cross-platform conversion smoke checks should be automated on Windows and Linux CI.
- Font provenance/licensing needs to be documented for every bundled font, especially non-OFL commercial families. The licensed MonoLisa and Operator Mono coding-font files are tracked and included in the Windows installer; the separate MonoLisa Text trial files and proportional Operator family are excluded. JetBrains Mono remains the redistributable default.
- A signed Windows installer would improve trust and reduce SmartScreen friction.
