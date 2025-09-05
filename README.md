
# Multilingual Markdown to PDF Generator

This project provides an automated workflow to convert Markdown training materials (Bengali, Arabic, English, Emoji, Symbols) into a professionally formatted PDF using Pandoc, XeLaTeX, custom fonts, and a Lua filter.

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

Put your Markdown file (e.g., `Mobile Servicing Training.md`) in the repo folder. For best results, separate Bengali, Arabic, and English sentences with blank lines.


### 4. Run the auto-convert script

```sh
./auto_convert_and_push.sh
```

- The script watches for changes and automatically converts your Markdown to PDF and pushes updates to GitHub.


### 5. Check your output PDF

Example: `Mobile_Servicing_Training.pdf` or `output/output.pdf`

---


## File Overview

- `template.tex` – Custom LaTeX template
- `multi-lang-font-filter.lua` – Pandoc Lua filter for Bengali, Arabic, emoji, and symbol handling
- `auto_convert_and_push.sh` – Automation script
- Example Markdown: `Mobile Servicing Training.md`
- `setup.md` – Detailed setup and customization guide

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

- Edit `template.tex` for layout, font, and page setup changes.
- Update the Lua filter for more Unicode ranges, font tweaks, or line break logic.
- See `setup.md` for advanced PDF customization (font size, margins, etc.).
- Add your own Markdown files for conversion.

---


## Credits

Prepared by: Md. Rabiul Islam

---


## License

[MIT](LICENSE) (or your preferred license)
