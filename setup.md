## 1. Prerequisites

- **Pandoc**: Document converter (https://pandoc.org/)
- **TeX Live (with XeLaTeX)**: LaTeX distribution supporting Unicode and custom fonts
- **Lua**: For Pandoc Lua filters
- **Fonts**:
  - Noto Sans (main)
  - Ekushey Lalsalu (Bengali)
  - Amiri (Arabic)
  - Noto Emoji (Emoji)
  - Symbola (Symbols)

### Install on Ubuntu/Debian
```fish
sudo apt update
sudo apt install pandoc texlive-xetex fonts-noto fonts-noto-cjk fonts-noto-color-emoji fonts-symbola
```
- For Bengali and Arabic fonts, download and place them in `~/.fonts` or update the font path in `template.tex`.

---

## 2. File Structure

- `input.md` : Your Markdown source file
- `template.tex` : Pandoc XeLaTeX template (customized for multilingual support)
- `multi-lang-font-filter.lua` : Pandoc Lua filter for font assignment and text escaping
- `auto_convert.sh` : Shell script to automate conversion
- `output/output.pdf` : Generated PDF

---

## 3. Usage

### Step 1: Prepare Your Markdown
- Write your content in `input.md`.
- For best results, separate Bengali, Arabic, and English sentences with blank lines.
- Images, tables, and horizontal rules are supported.

### Step 2: Run the Conversion Script
```fish
./auto_convert.sh
```
- This will run Pandoc with the template and Lua filter, producing `output/output.pdf`.

---

## 4. Customization

- **Fonts**: Edit `template.tex` to change font families or paths.
- **Lua Filter**: Edit `multi-lang-font-filter.lua` to adjust language detection or font wrapping logic.
- **Template**: Modify section formatting, TOC, geometry, etc. in `template.tex`.

---

## 5. Troubleshooting

- **Arabic/Bengali not rendering correctly?**
  - Ensure fonts are installed and paths are correct in `template.tex`.
  - Check that the Lua filter wraps text with `\ar{...}` for Arabic and `\bn{...}` for Bengali.
- **Missing characters warnings?**
  - Font may not support the required glyphs. Use Amiri for Arabic, Ekushey Lalsalu for Bengali.
- **PDF not generated?**
  - Check for errors in the terminal. Ensure Pandoc, XeLaTeX, and Lua are installed.

---

## 6. Advanced

- **Manual Conversion**:
  ```fish
  pandoc input.md --template=template.tex --lua-filter=multi-lang-font-filter.lua -o output/output.pdf
  ```
- **Add new language support**:
  - Update `template.tex` with a new font family and command.
  - Extend the Lua filter to detect and wrap the new language.

---

## 7. PDF Customization: Font Size, Page Setup, and More

You can customize the appearance of your generated PDF by editing `template.tex`. Below are common options:

### Font Size

- The document class line sets the base font size:
  ```latex
  \documentclass[12pt]{extarticle}
  ```
- Change `12pt` to another value (e.g., `10pt`, `11pt`, `14pt`) for smaller or larger text.

### Page Setup & Margins

- The geometry package controls page size and margins:
  ```latex
  \geometry{a4paper, margin=1in}
  ```
- Change `a4paper` to `letterpaper` or adjust `margin` for more or less whitespace.

### Line Spacing

- Adjust line spacing with:
  ```latex
  \linespread{1.1}
  ```
- Increase for more space between lines (e.g., `1.2`), decrease for tighter text.

### Section & Heading Styles

- Controlled by the `titlesec` package. Edit the `\titleformat` commands to change alignment, font size, or style.

### Table of Contents

- Remove or move the TOC by editing the `\tableofcontents` line in `template.tex`.

### Page Numbers

- Page numbering is disabled by default (`\pagenumbering{gobble}`). To enable, change to `\pagenumbering{arabic}`.

### Custom Fonts

- Change font families by editing the `\setmainfont`, `\newfontfamily` commands. Ensure the fonts are installed and paths are correct.

### Other Features

- Add or remove packages for advanced features (e.g., color, code highlighting, headers/footers).

---

**Tip:** After making changes to `template.tex`, re-run `auto_convert.sh` to see the effect in your PDF.
# Setup Guide: Multilingual Markdown to PDF Conversion

This guide explains how to set up and use the provided Pandoc + XeLaTeX workflow for generating PDFs from Markdown files with Bengali, Arabic, Emoji, Symbol, and English text support.

---

## 8. References
- [Pandoc User Guide](https://pandoc.org/MANUAL.html)
- [XeLaTeX Documentation](https://www.latex-project.org/get/#tex)
- [Lua Filters in Pandoc](https://pandoc.org/lua-filters.html)

---

## 9. Contact
For help, contact the repository owner or open an issue on GitHub.
