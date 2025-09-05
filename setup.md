## 1. Prerequisites

- **Pandoc**: Document converter (https://pandoc.org/)
- **TeX Live (with XeLaTeX)**: LaTeX distribution supporting Unicode and custom fonts
- **Lua**: For Pandoc Lua filters
- **Fonts**:
- [Noto Sans](https://fonts.google.com/noto/specimen/Noto+Sans)
- [Noto Emoji](https://fonts.google.com/noto/specimen/Noto+Emoji)
- [Symbola](https://fontlibrary.org/en/font/symbola)
- [Ekushey Lalsalu](https://okkhor52.com/download.html?id=_009)
- [Amiri (Google Fonts)](https://fonts.google.com/specimen/Amiri)
- [Amiri (GitHub)](https://github.com/aliftype/amiri)


### Install on Ubuntu/Debian
```fish
sudo apt update
sudo apt install pandoc texlive-xetex fonts-noto fonts-noto-cjk fonts-noto-color-emoji fonts-symbola
```
- For Bengali and Arabic fonts, download and place them in `~/.fonts` or update the font path in `template.tex`.

---

## 2. File Structure

 - `input.md` : Your Markdown source file
 - `template.tex` : Pandoc XeLaTeX template for multilingual PDF
 - `multi-lang-font-filter.lua` : Pandoc Lua filter for Bengali, Arabic, emoji, and symbol handling
 - `convert_to_pdf.sh` : Manual conversion script
 - `auto_convert_and_push.sh` : Automation script (watches for changes, converts to PDF, and pushes to GitHub)
 - `output/` : Output directory for generated PDFs
 - `output/output.pdf` : Main generated PDF
 - `setup.md` : Detailed setup and customization guide

---

## 3. Usage

### Step 1: Prepare Your Markdown
- Write your content in `input.md`.
- For best results, separate Bengali, Arabic, and English sentences with blank lines.
- Images, tables, and horizontal rules are supported.

### Step 2: Run the Conversion Script

Manual conversion:
```fish
./convert_to_pdf.sh
```
Automatic conversion and push:
```fish
./auto_convert_and_push.sh
```
Both scripts will use the template and Lua filter, producing `output/output.pdf`.

---

## 4. Customization

 - **Edit `template.tex`** to change layout, fonts, page size, margins, line spacing, and section styles. See below for details on customizing font size, page setup, and more.
 - **Edit `multi-lang-font-filter.lua`** to adjust language detection, font assignment, or add support for new Unicode ranges and line break logic.
 - **Edit `input.md`** for your content. This is the only source file used for conversion.
 - For advanced PDF options and troubleshooting, refer to the rest of this setup guide.

---

## 5. Troubleshooting

- **Arabic/Bengali not rendering correctly?**
  - Ensure the required fonts are installed and the font paths in `template.tex` are correct.
  - The Lua filter should wrap Arabic text with `\ar{...}` and Bengali text with `\bn{...}`. Check your Markdown and filter output.
- **Missing characters or font warnings?**
  - The selected font may not support all glyphs. Use Amiri for Arabic and Ekushey Lalsalu for Bengali. For emoji and symbols, use Noto Emoji and Symbola.
- **PDF not generated or errors during conversion?**
  - Check the terminal for error messages. Make sure Pandoc, XeLaTeX, and Lua are installed and available in your PATH.
  - Review the output for LaTeX errors (e.g., line break issues, missing packages) and adjust your Markdown or template as needed.

---

## 6. Advanced

- **Manual Conversion:**
  Run Pandoc directly for custom options:
  ```fish
  pandoc input.md --template=template.tex --lua-filter=multi-lang-font-filter.lua -o output/output.pdf
  ```

- **Automatic Conversion and Push:**
  Use the automation script for continuous conversion and GitHub push:
  ```fish
  ./auto_convert.sh
  ```

- **Add new language support:**
  - Update `template.tex` with a new font family and LaTeX command for the language.
  - Extend `multi-lang-font-filter.lua` to detect and wrap the new language text.

---

## 7. PDF Customization: Font Size, Page Setup, and More


You can customize the appearance of your generated PDF by editing `template.tex`. Common options include:

**Font Size:**
- Change the base font size in the document class line:
  ```latex
  \documentclass[12pt]{extarticle}
  ```
- Use `10pt`, `11pt`, `12pt`, or `14pt` for different text sizes.

**Page Setup & Margins:**
- Adjust page size and margins with the geometry package:
  ```latex
  \geometry{a4paper, margin=1in}
  ```
- Change `a4paper` to `letterpaper` or modify `margin` for more/less whitespace.

**Line Spacing:**
- Set line spacing with:
  ```latex
  \linespread{1.1}
  ```
- Increase for more space (e.g., `1.2`), decrease for tighter text.

**Section & Heading Styles:**
- Controlled by the `titlesec` package. Edit `\titleformat` commands for alignment, font size, or style.

**Table of Contents:**
- Remove or move the TOC by editing the `\tableofcontents` line in `template.tex`.

**Page Numbers:**
- Page numbering is disabled by default (`\pagenumbering{gobble}`). To enable, change to `\pagenumbering{arabic}`.

**Custom Fonts:**
- Change font families by editing `\setmainfont`, `\newfontfamily` commands. Ensure fonts are installed and paths are correct.

**Other Features:**
- Add or remove LaTeX packages for advanced features (color, code highlighting, headers/footers, etc.).

**Tip:** After making changes to `template.tex`, re-run `auto_convert.sh` to see the effect in your PDF.

# Setup Guide: Multilingual Markdown to PDF Conversion

This guide explains how to set up and use the provided Pandoc + XeLaTeX workflow for generating PDFs from Markdown files with Bengali, Arabic, Emoji, Symbol, and English text support.

---

## 8. References

- [Pandoc Documentation](https://pandoc.org/MANUAL.html)
- [Lua Filters in Pandoc](https://pandoc.org/lua-filters.html)
- [XeLaTeX Documentation](https://www.latex-project.org/get/#tex-distributions)
- [Noto Sans](https://fonts.google.com/noto/specimen/Noto+Sans)
- [Noto Emoji](https://fonts.google.com/noto/specimen/Noto+Emoji)
- [Symbola](https://fontlibrary.org/en/font/symbola)
- [Ekushey Lalsalu](https://okkhor52.com/download.html?id=_009)
- [Amiri (Google Fonts)](https://fonts.google.com/specimen/Amiri)
- [Amiri (GitHub)](https://github.com/aliftype/amiri)

---

## 9. Contact

For questions, bug reports, or feature requests, please open an issue on the [GitHub repository](https://github.com/rabiul121/md-to-pdf) or contact the maintainer:

- **GitHub:** [rabiul121](https://github.com/rabiul121)
- **Email:** <robiulislam649@gmail.com>
