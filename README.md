# Multilingual Markdown to PDF Generator

An automated, cross-platform workflow to convert multilingual Markdown documents (Bengali, Arabic, English, Emojis, Symbols) into professionally formatted PDFs using **Pandoc**, **XeLaTeX**, and a custom **Lua filter**.

---

## Features

- **Multilingual Unicode Rendering**:
  - **Bengali**: Powered by **SolaimanLipi** (with Bold support)
  - **Arabic**: Powered by **Amiri** with right-to-left paragraph direction and right alignment for Arabic-containing paragraphs.
  - **English & General**: Powered by bundled **DejaVu Sans** by default, with additional font choices in the UI.
  - **Icons, Emojis & Symbols**: Uses Windows' Segoe UI families or bundled Noto families on Linux.
- **Responsive Layout & Margin Overflow Prevention**:
  - Automatically balances inter-word spacing (`\sloppy`, `\emergencystretch`) so text never cuts off or overflows the margins, even on narrow mobile dimensions.
  - Automatically wraps long URLs at any character using `xurl`.
- **Page Size Presets**:
  - **A4**, **Letter**, **A5**, **Legal**, and preset reading layouts.
  - **For Mobile**: Smartphone-tailored reading layout (100mm × 160mm, narrow margins, no zooming required).
  - **For PC**: A4 widescreen layout with comfortable desktop reading margins.
- **Document Layout Controls**:
  - Select English, heading, Bengali, and Arabic fonts independently. Search installed font families from the font search fields; bundled project fonts remain first.
  - Use page-appropriate default margins (including compact mobile margins), choose common presets, or enter a custom dimension.
  - Set portrait or landscape orientation.
  - Toggle page numbers; choose Arabic or Roman numerals, formats such as `Page 1 of 10` or `1 / 10`, footer position, and text size.
  - Configure TOC/front-matter numbering independently, including whether it appears, style, format, language, footer position, and size. Main-content numbering restarts at 1 in its selected style after the TOC.
  - Configure first-line paragraph indentation, heading alignment, and heading boldness.
  - Toggle hyphenation and set line height from the GUI or CLI.
  - Enable **Copy-friendly text** to embed XeTeX ActualText mappings for complex-script glyphs; it is off by default and does not change page appearance. Arabic copy order may still vary by PDF reader.
  - Set paragraph spacing using None, Compact, Normal, Relaxed, or a custom TeX dimension.
  - Include an optional table of contents with selectable left/center/right alignment and Classic, Minimal, or Decorative design.
  - The TOC title (`Table of Contents` or `সূচিপত্র`) uses a consistent 16pt size. Wrapped TOC entries align to the left edge, with leaders and page numbers aligned consistently.
- **Light and Dark UI Themes**: Switch the desktop interface theme while the application is open.
- **Font Size Presets**:
  - Standard (11pt), Medium (14pt), Large (17pt), or Custom (8pt - 36pt).
- **Modern Graphical UI & Interactive CLI**:
  - Native desktop UI window with file picker, preset selectors, batch selection, and live conversion log.
  - Interactive terminal CLI wizard for headless/SSH environments.
- **Input Formats**: Markdown, text, Word `.doc`/`.docx`, EPUB, and MOBI. Pandoc reads Markdown, text, DOCX, and EPUB directly; legacy DOC needs LibreOffice, and MOBI needs Calibre's `ebook-convert` command.
- **Output Controls**: Choose a custom PDF filename and destination folder, then open the output folder from the UI. Existing files are preserved; collisions use incrementing names such as `document_1.pdf` and `document_2.pdf`.
- **Multilingual Layout**: Arabic-containing paragraphs are right-to-left and right-aligned. Bangla page labels render both current and total page digits in Bengali; TOC title alignment, design, and title size are configurable.
- **Saved Profiles**: Quick presets include Mobile, PC, English, Bangla, Minimal, and Decorative. Select a profile to apply its values to the visible options; save named profiles in `profiles.json`. The GUI also restores the last-used customization on the next launch.
- **Profile Safety**: Editing any setting marks the current profile as Custom. Built-in presets cannot be overwritten or deleted; save an edited preset under a custom name. User-created profiles can be updated or deleted.
- **Auto-Convert (Watch Mode)**: Continuously monitors the selected input file and re-converts it when saved.

---

## Project Structure

```
md-to-pdf/
├── run.bat / run.sh            # Double-click to launch (Windows / Linux)
├── main.py                     # Python entry point (python main.py)
├── __main__.py                 # Enables: python . (same as python main.py)
├── pyproject.toml              # Package metadata and pytest config
├── requirements.txt            # Dependency notes (no PyPI packages needed)
├── src/                        # Converter, template, and Lua filter
├── assets/fonts/               # Bundled font families
├── scripts/                    # Windows and Linux setup/CLI wrappers
├── launchers/                  # Shared GUI, CLI, and watch launchers
├── input/                      # Sample source documents
├── output/                     # Generated PDFs (ignored by Git)
├── tests/                      # Regression tests and fixtures
└── README.md
```

---

## 1. Quick Installation

### On Windows
Run the automated installer by double-clicking:
```cmd
scripts\windows\setup.bat
```
*Or in PowerShell:*
```powershell
.\scripts\windows\setup.ps1
```

**What it installs:**
1. **Pandoc**, **Python 3**, and **XeLaTeX / MiKTeX** (using `winget`, with `scoop` as a fallback).
2. Redistributable fonts in `assets/fonts/`, registered for the current Windows user.

Segoe UI Emoji and Segoe UI Symbol are Windows system fonts. They are not distributed by this project; on Windows the converter uses locally supplied font files when present and otherwise requests the installed system font families.

---

### On Linux or WSL (Debian / Ubuntu)
Run the automated setup script:
```bash
chmod +x scripts/linux/*.sh
./scripts/linux/setup.sh
```

The setup script installs Python 3, Pandoc, XeLaTeX, the Arabic/LaTeX packages, Noto/Symbola fallback fonts, and copies the redistributable project fonts into your user font directory. It supports Debian/Ubuntu systems with `apt-get` and requires `sudo` when not run as root.

### Launch and convert

| Platform | GUI | CLI | Watch one file |
| --- | --- | --- | --- |
| Windows | `run.bat` | `scripts\windows\cli_convert.bat` | `scripts\windows\cli_watch.bat` |
| Linux / WSL | `bash run.sh` | `bash scripts/linux/cli_convert.sh` | `bash scripts/linux/cli_watch.sh` |

The platform scripts all dispatch to the same Python application, so EPUB support, saved options, output naming, and conversion behavior are consistent. Python 3, Pandoc, and XeLaTeX are required. Windows PowerShell users can also run `scripts/windows/setup.ps1` directly.

---

## 2. How to Use

### Option A: Modern Graphical UI (Recommended)

1. **Windows:** Double-click `run.bat` from the project root.
   - PowerShell: `./launchers/start.ps1`
   - Linux: `bash ./run.sh` (use `--cli` for the terminal wizard)
   - *(or run `python main.py` or `python .` in terminal)*
2. The UI window opens:
  - **1. Select Input File**: Click **Browse...** for one supported document or **Batch...** for multiple documents.
  - Set an optional output filename and destination folder; batch conversion keeps each input's basename.
  - **2. Page Setup**: Choose paper size, portrait/landscape orientation, and a margin preset or custom margin.
  - **3. Select Font Size**: Choose *Standard (11pt)*, *Medium (14pt)*, *Large (17pt)*, or enter a *Custom* size.
  - **4. Typography and Document Layout**: Related settings are grouped into **Typography**, **TOC & Page Numbers**, and **Profiles** tabs. Bengali TOCs also use Bengali page digits, independently of footer-number language.
  - **5. Theme and Mode**: Switch between light/dark UI and choose *Convert Once* or *Auto-Convert on File Save*.
3. Click **🚀 Start PDF Conversion**.
4. When finished, use **📂 Open PDF** or **Open output folder**.

---

### Option B: Terminal / CLI Wizard

If running inside PowerShell, CMD, or a Linux terminal/SSH:

The CLI scripts delegate to the unified Python application; Python 3 is required. This keeps conversion, saved settings, output naming, and watch behavior consistent across platforms.
The CLI accepts several custom input paths separated by semicolons, or `A` to convert all supported files listed in `input/`.

#### On Windows:
```powershell
# Manual interactive wizard
.\launchers\start.ps1 -Cli

# Auto-convert watcher (recompiles on file save)
.\scripts\windows\cli_watch.ps1
```

#### On Linux / WSL:
```bash
# Manual interactive wizard
bash launchers/start.sh --cli

# Auto-convert watcher (recompiles on file save)
./scripts/linux/cli_watch.sh
```

---

## Future App

A dedicated Windows/Android app is a future direction; the current implementation is a cross-platform Python desktop UI and CLI.

---

## 3. Customization & Advanced Options

### Customizing Fonts
Redistributable project fonts are stored under `assets/fonts/` and installed by the setup scripts. Windows system fonts are not included. App-specific font selection is passed to the template in `src/template.tex`:
```latex
\setmainfont{DejaVu Sans}
\newfontfamily\bengalifont[Script=Bengali]{SolaimanLipi}
\newfontfamily\emojifont{Noto Emoji}
\newfontfamily\symbolfont{Noto Sans Symbols 2}
\newfontfamily\arabicfont[Script=Arabic]{Amiri}
```
- To switch Bengali to another font (e.g., *Noto Sans Bengali*, *Kalpurush*, or *Ekushey Lalsalu*), update `\newfontfamily\bengalifont[Script=Bengali]{FontName}`.
- On Windows the converter uses locally available Segoe UI Emoji/Symbol font files when present, otherwise the installed Windows font families. Linux uses the bundled Noto families.
- Fonts selected in the UI or CLI must be installed and discoverable by XeLaTeX on the current system.

### Customizing Margins and Geometry
You can pass custom dimensions directly to Pandoc via `-V geometry`:
```bash
pandoc input/input.md -o output/output.pdf \
  --pdf-engine=xelatex \
  --template=src/template.tex \
  --lua-filter=src/font_filter.lua \
  -V geometry:paperwidth=120mm -V geometry:paperheight=180mm -V geometry:margin=10mm
```

### Line Spacing
Use the **Line height** control in the UI or enter a multiplier in the CLI wizard. The template default is set by the conversion options; its LaTeX directive is:
```latex
\linespread{1.1}
```

---

## 4. Troubleshooting

- **Text cutting off or extending past right margin:**
  - `src/template.tex` includes `\sloppy`, `\emergencystretch 3em`, and `\usepackage{xurl}`. If you have an exceptionally long unbroken string or code block, decrease font size or verify words contain spaces/hyphens.
- **MiKTeX / XeLaTeX font not found:**
  - Verify that the font name in `src/template.tex` matches the name shown by `fc-list : family` (Linux) or Windows Fonts Control Panel.
- **A PDF cannot be written:**
  - The converter avoids overwriting an existing PDF by choosing the next available `_N` filename. Close the PDF if a viewer still has it locked, or choose a different output folder.
- **Missing LaTeX packages:**
  - On Windows, MiKTeX automatically downloads missing packages on first use.
  - On Linux, ensure `texlive-latex-extra` and `texlive-fonts-recommended` are installed.
