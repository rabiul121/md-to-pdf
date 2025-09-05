
# Multilingual Markdown to PDF Generator

This project provides an automated workflow to convert multilingual Markdown training materials (Bengali, Arabic, English, Emoji, Symbols) from `input.md` into a professionally formatted PDF using Pandoc, XeLaTeX, custom fonts, and a Lua filter.

---


## Features

- **Bengali, Arabic, and English Unicode support**
- **Emoji and symbol rendering** (with fallback fonts)
- **Custom LaTeX template** for clean, readable PDFs
- **Automatic PDF regeneration and GitHub push** via shell script
- **Lua filter** for Bengali, Arabic, emoji, and symbol font handling

---

## Getting Started

### 1. Clone the repository

```sh
git clone https://github.com/yourusername/md-to-pdf.git
cd md-to-pdf
```


### 2. Install dependencies

- **Pandoc**
- **XeLaTeX** (TeX Live or similar)
- **Fonts:** Noto Sans, Noto Emoji, Symbola, Ekushey Lalsalu, Amiri (Arabic)
- **inotify-tools** (for auto script)

**Example (Ubuntu):**
```sh
sudo apt-get install pandoc texlive-xetex fonts-noto fonts-noto-cjk fonts-noto-color-emoji fonts-symbola inotify-tools
```


### 3. Place your Markdown file

Edit your content in `input.md` (this is the source file for conversion). For best results, separate Bengali, Arabic, and English sentences with blank lines.


### 4. Convert your Markdown to PDF

You have two options:

- **Manual conversion:**
	```sh
	./convert_to_pdf.sh
	```
	This will convert `input.md` to `output/output.pdf` using Pandoc, XeLaTeX, and the Lua filter.

- **Automatic conversion and push:**
	```sh
	./auto_convert.sh
	```
	This script watches for changes in `input.md`, automatically converts to PDF, and pushes updates to GitHub.


### 5. Check your output PDF

Example: `output/output.pdf`

---


## File Overview

`input.md` – Your Markdown source file
`template.tex` – Custom LaTeX template for multilingual PDF
`multi-lang-font-filter.lua` – Pandoc Lua filter for Bengali, Arabic, emoji, and symbol handling
`convert_to_pdf.sh` – Manual conversion script
`auto_convert.sh` – Automation script (watches for changes in file, converts into PDF, and pushes to GitHub)
`output/` – Output directory for generated PDFs
`output/output.pdf` – Main generated PDF
`setup.md` – Detailed setup and customization guide

---

## GitHub & Privacy

**Note:**
This project does **not** contain any personal Git configuration or credentials.
Before using the script, make sure you have set your own Git username and email:

```sh
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

**Never** add personal access tokens or passwords to this script.

---


## Customization

- **Edit `template.tex`** to change layout, fonts, page size, margins, line spacing, and section styles. See `setup.md` for details on customizing font size, page setup, and more.
- **Edit `multi-lang-font-filter.lua`** to adjust language detection, font assignment, or add support for new Unicode ranges and line break logic.
- **Edit `input.md`** for your content. This is the only source file used for conversion.
- For advanced PDF options and troubleshooting, refer to `setup.md`.

---


## Credits


Prepared by: Md. Rabiul Islam

This project is open source. Contributions, suggestions, and improvements are welcome via GitHub issues or pull requests.

---


## License


This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
