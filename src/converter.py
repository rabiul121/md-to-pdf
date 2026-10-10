"""
Multilingual Markdown to PDF Converter (Windows & Linux)
Supports: Bengali (SolaimanLipi), Arabic (Amiri), English, Emojis, and Symbols
"""

import os
import sys
import time
import shutil
import subprocess
import threading
import tempfile
import json
import re
from pathlib import Path

from src.core.engine import font_style_features
from src.core.images import prepare_remote_images
from src.core.editor import escape_plain_text

# Base directories - resolves the project root whether launched from src/ or a wrapper.
_here = Path(__file__).resolve().parent
BASE_DIR = _here.parent if (_here.parent / "assets" / "fonts").exists() else _here
APP_DIR = _here
INPUT_DIR = BASE_DIR / "input"
TEMPLATE_PATH = APP_DIR / "template.tex"
LUA_FILTER_PATH = APP_DIR / "font_filter.lua"
OUTPUT_DIR = BASE_DIR / "output"
PROFILE_PATH = BASE_DIR / "profiles.json"
LAST_USED_PROFILE = "_last_used"
SUPPORTED_INPUT_EXTENSIONS = {".md", ".markdown", ".txt", ".doc", ".docx", ".epub", ".mobi"}

# Page sizes and margin presets are passed separately so users can combine them.
PAGE_SIZES = {
    "A4": ["a4paper"],
    "Letter": ["letterpaper"],
    "A5": ["a5paper"],
    "Legal": ["legalpaper"],
    "For Mobile": ["paperwidth=100mm", "paperheight=160mm"],
    "For PC": ["a4paper"],
}
MARGIN_PRESETS = {
    "Narrow (0.5 in)": "0.5in",
    "Standard (1 in)": "1in",
    "Wide (1.25 in)": "1.25in",
    "Wide (1.5 in)": "1.5in",
    "Compact (7 mm)": "7mm",
}
PAGE_DEFAULT_MARGINS = {"For Mobile": "7mm", "For PC": "1.2in"}

# Font size presets (supported by extarticle: 8, 9, 10, 11, 12, 14, 17, 20)
FONT_SIZES = {
    "Standard": "11pt",
    "Medium": "14pt",
    "Large": "17pt"
}

PROJECT_FONT_CHOICES = {
    "English": [
        "DejaVu Sans", "Noto Sans", "Noto Serif", "Source Serif 4", "Inter", "JetBrains Mono",
        "EB Garamond", "Georgia", "Sabon", "Adobe Garamond", "Minion Pro", "Alegreya",
        "Alegreya Sans", "Palatino Linotype", "Crimson Text", "Della Respira", "Sylfaen",
    ],
    "Bengali": ["SolaimanLipi", "Noto Sans Bengali", "Noto Serif Bengali", "Kalpurush", "Ekushey Lalsalu"],
    "Arabic": ["Amiri", "Noto Naskh Arabic", "Noto Sans Arabic", "Scheherazade New"],
}
HEADING_FONT_CHOICES = [
    *PROJECT_FONT_CHOICES["English"], "Helvetica", "Arial", "Baskerville", "Libre Baskerville", "Futura", "Playfair Display",
]

PROFILE_BASE_SETTINGS = {
    "page_size_choice": "A4", "orientation": "Portrait", "margin_choice": "Page default",
    "custom_margin": "25mm", "font_size_choice": "Medium", "custom_font_size": 14,
    "english_font": "DejaVu Sans", "heading_font": "DejaVu Sans",
    "bengali_font": "SolaimanLipi", "arabic_font": "Amiri",
    "page_numbers": False, "page_number_style": "arabic", "page_number_format": "Page 1 of 10",
    "page_number_position": "Middle", "page_number_size": "9pt", "page_number_language": "English",
    "front_page_numbers": False, "front_page_number_style": "roman", "front_page_number_format": "1",
    "front_page_number_position": "Middle", "front_page_number_size": "9pt", "front_page_number_language": "English",
    "indent_first_line": False, "indent_amount": "0.25in", "center_headings": True,
    "bold_headings": True, "paragraph_spacing": "6pt", "include_toc": True, "beautify_toc": True,
    "toc_language": "English", "toc_alignment": "Center", "toc_design": "Classic",
    "page_border": False, "hyphenation": True, "line_height": "1.1",
    "copy_friendly_text": False,
    "output_name": "", "output_directory": str(OUTPUT_DIR),
}

BUILT_IN_PROFILES = {
    "Mobile": {"page_size_choice": "For Mobile", "font_size_choice": "Standard", "line_height": "1.0", "margin_choice": "Page default"},
    "PC": {"page_size_choice": "For PC", "font_size_choice": "Medium", "line_height": "1.15", "margin_choice": "Page default"},
    "English": {"toc_language": "English", "page_number_language": "English", "english_font": "DejaVu Sans"},
    "Bangla": {"toc_language": "Bangla", "page_number_language": "Bangla", "bengali_font": "SolaimanLipi"},
    "Book Print - EB Garamond": {
        "page_size_choice": "A5", "font_size_choice": "Standard", "english_font": "EB Garamond",
        "heading_font": "Playfair Display", "margin_choice": "Standard (1 in)", "line_height": "1.15",
        "indent_first_line": True, "paragraph_spacing": "0pt", "page_numbers": True,
    },
    "Book Print - Alegreya": {
        "page_size_choice": "A5", "font_size_choice": "Standard", "english_font": "Alegreya",
        "heading_font": "Alegreya Sans", "margin_choice": "Standard (1 in)", "line_height": "1.15",
        "indent_first_line": True, "paragraph_spacing": "0pt", "page_numbers": True,
    },
    "Book Print - Crimson Text": {
        "page_size_choice": "A5", "font_size_choice": "Standard", "english_font": "Crimson Text",
        "heading_font": "Baskerville", "margin_choice": "Standard (1 in)", "line_height": "1.15",
        "indent_first_line": True, "paragraph_spacing": "0pt", "page_numbers": True,
    },
    "Book Print - Georgia": {
        "page_size_choice": "A5", "font_size_choice": "Standard", "english_font": "Georgia",
        "heading_font": "Arial", "margin_choice": "Standard (1 in)", "line_height": "1.15",
        "indent_first_line": True, "paragraph_spacing": "0pt", "page_numbers": True,
    },
    "Minimal": {"toc_design": "Minimal", "beautify_toc": False, "page_border": False},
    "Decorative": {"toc_design": "Decorative", "beautify_toc": True, "page_border": True},
}

BUNDLED_FONT_FILES = {
    "english": {
        "DejaVu Sans": "DejaVuSans-Regular.ttf",
        "Noto Sans": "NotoSans-VariableFont_wdth,wght.ttf",
        "Noto Serif": "NotoSerif-VariableFont_wdth,wght.ttf",
        "Source Serif 4": "SourceSerif4-VariableFont_opsz,wght.ttf",
        "Inter": "Inter-VariableFont_opsz,wght.ttf",
        "JetBrains Mono": "JetBrainsMono-VariableFont_wght.ttf",
        "EB Garamond": "EBGaramond-Variable.ttf",
        "Georgia": "Georgia-Regular.ttf",
        "Sabon": "Sabon-Regular.ttf",
        "Adobe Garamond": "AdobeGaramondPro-Regular.otf",
        "Minion Pro": "MinionPro-Regular.otf",
        "Alegreya": "Alegreya-Variable.ttf",
        "Alegreya Sans": "AlegreyaSans-Regular.ttf",
        "Palatino Linotype": "PalatinoLinotype-Regular.ttf",
        "Crimson Text": "CrimsonText-Regular.ttf",
        "Della Respira": "DellaRespira-Regular.ttf",
        "Sylfaen": "Sylfaen-Regular.ttf",
        "Baskerville": "Baskerville-Regular.ttf",
        "Libre Baskerville": "LibreBaskerville-Variable.ttf",
        "Helvetica": "Helvetica.ttf",
        "Arial": "Arial-Regular.ttf",
        "Futura": "FuturaLTPro-Book.otf",
        "Playfair Display": "PlayfairDisplay-Variable.ttf",
    },
    "bengali": {
        "SolaimanLipi": "SolaimanLipi-Regular.ttf",
        "Noto Sans Bengali": "NotoSansBengali-VariableFont_wdth,wght.ttf",
        "Noto Serif Bengali": "NotoSerifBengali-VariableFont_wdth,wght.ttf",
        "Kalpurush": "Kalpurush-Regular.ttf",
        "Ekushey Lalsalu": "EkusheyLalsalu-Regular.ttf",
    },
    "arabic": {
        "Amiri": "Amiri-Regular.ttf",
        "Noto Naskh Arabic": "NotoNaskhArabic-VariableFont_wght.ttf",
        "Noto Sans Arabic": "NotoSansArabic-VariableFont_wdth,wght.ttf",
        "Scheherazade New": "ScheherazadeNew-Regular.ttf",
    },
    "symbol": {
        "Noto Emoji": "NotoEmoji-VariableFont_wght.ttf",
        "Noto Sans Symbols 2": "NotoSansSymbols2-Regular.ttf",
        "Segoe UI Emoji": "seguiemj.ttf",
        "Segoe UI Symbol": "seguisym.ttf",
    },
}


def resolve_bundled_font(family, role):
    """Return a fontspec filename/path pair for a bundled family, if available."""
    filename = BUNDLED_FONT_FILES.get(role, {}).get(family)
    if not filename:
        return None
    font_path = BASE_DIR / "assets" / "fonts" / role / filename
    if not font_path.is_file():
        return None
    return filename, font_path.resolve().parent.as_posix() + "/"


def resolve_font_file(family, role):
    """Resolve a bundled or installed family to fontspec filename and Path."""
    bundled_font = resolve_bundled_font(family, role)
    if bundled_font:
        return bundled_font

    ensure_env_path()
    font_match = shutil.which("fc-match")
    if not font_match or not family.strip():
        return None
    try:
        result = subprocess.run(
            [font_match, "-f", "%{family}\n%{file}", family],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    lines = result.stdout.splitlines()
    if len(lines) < 2:
        return None
    family_aliases = {alias.strip().casefold() for alias in lines[0].split(",")}
    if family.casefold() not in family_aliases:
        return None
    font_path = Path(lines[1].strip())
    if not font_path.is_file():
        return None
    return font_path.name, font_path.resolve().parent.as_posix() + "/"


def font_file_supports_codepoint(font_selection, codepoint):
    """Check installed font coverage with fontconfig, when available."""
    if not font_selection:
        return False
    font_file, font_directory = font_selection
    font_path = Path(font_directory) / font_file
    fc_query = shutil.which("fc-query")
    if not fc_query or not font_path.is_file():
        return False
    result = subprocess.run(
        [fc_query, "-f", "%{charset}", str(font_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return False

    for charset_range in result.stdout.split():
        clean_range = charset_range.strip().rstrip(",")
        if not clean_range:
            continue
        try:
            if "-" in clean_range:
                bounds = clean_range.split("-", 1)
                start = int(bounds[0], 16)
                end = int(bounds[1], 16) if len(bounds) == 2 and bounds[1].strip() else start
            else:
                start = int(clean_range, 16)
                end = start
            if start <= codepoint <= end:
                return True
        except ValueError:
            continue
    return False


def available_output_path(output_path):
    """Return the requested path or the first unused _N variant."""
    if not output_path.exists():
        return output_path

    index = 1
    while True:
        candidate = output_path.with_name(f"{output_path.stem}_{index}{output_path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def filter_font_families(query, families):
    """Filter a font-family list by case-insensitive substring."""
    query = query.strip().casefold()
    if query == "search fonts":
        query = ""
    return [family for family in families if query in family.casefold()] if query else list(families)


def get_font_families(root, project_fonts):
    """Return project font options first, followed by installed system fonts A-Z."""
    try:
        from tkinter import font as tkinter_font
        installed_fonts = tkinter_font.families(root)
    except Exception:
        installed_fonts = []

    project_fonts = list(dict.fromkeys(project_fonts))
    project_names = {name.casefold() for name in project_fonts}
    system_fonts = sorted(
        {name for name in installed_fonts if name.casefold() not in project_names},
        key=str.casefold,
    )
    return project_fonts + system_fonts

def ensure_env_path():
    """Ensure XeLaTeX and Pandoc are in PATH (especially for Windows scoop/miktex)."""
    if sys.platform.startswith("win"):
        current_path = os.environ.get("Path", "")
        scoop_miktex = Path(os.environ.get("USERPROFILE", "")) / "scoop" / "apps" / "miktex" / "current" / "texmfs" / "install" / "miktex" / "bin" / "x64"
        if scoop_miktex.exists() and str(scoop_miktex) not in current_path:
            os.environ["Path"] = str(scoop_miktex) + os.pathsep + current_path

def find_executable(name):
    """Find executable in PATH or known fallback locations."""
    ensure_env_path()
    found = shutil.which(name)
    if found:
        return found
    if sys.platform.startswith("win"):
        if name == "pandoc":
            cand = Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc" / "pandoc.exe"
            if cand.exists():
                return str(cand)
        elif name == "xelatex":
            cand = Path(os.environ.get("USERPROFILE", "")) / "scoop" / "apps" / "miktex" / "current" / "texmfs" / "install" / "miktex" / "bin" / "x64" / "xelatex.exe"
            if cand.exists():
                return str(cand)
    return None

def convert_md_to_pdf(input_file, page_size_choice="A4", font_size_choice="Medium", custom_font_size=None, output_file=None, log_func=print, english_font="DejaVu Sans", bengali_font="SolaimanLipi", arabic_font="Amiri", margin_choice="Page default", custom_margin=None, orientation="Portrait", page_numbers=False, page_number_style="arabic", page_number_format="Page 1 of 10", page_number_position="Middle", page_number_size="9pt", front_page_numbers=False, front_page_number_style="roman", front_page_number_format="1", front_page_number_position="Middle", front_page_number_size="9pt", front_page_number_language="English", indent_first_line=False, indent_amount="0.25in", center_headings=True, bold_headings=True, include_toc=True, beautify_toc=True, output_name=None, output_directory=None, toc_language="English", page_number_language="English", page_border=False, toc_alignment="Center", toc_design="Classic", heading_font="DejaVu Sans", hyphenation=True, line_height="1.1", paragraph_spacing="6pt", copy_friendly_text=False, input_format=None):
    """Convert a supported document to PDF using Pandoc and XeLaTeX."""
    ensure_env_path()

    input_path = Path(input_file).resolve()
    if not input_path.exists():
        log_func(f"[ERROR] Input file '{input_path}' does not exist.")
        return False, f"Input file '{input_path}' not found."

    if input_path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
        err = f"Unsupported input type '{input_path.suffix}'. Supported types: {', '.join(sorted(SUPPORTED_INPUT_EXTENSIONS))}."
        log_func(f"[ERROR] {err}")
        return False, err

    pandoc_bin = find_executable("pandoc")
    if not pandoc_bin:
        err = "Pandoc was not found. Please install Pandoc."
        log_func(f"[ERROR] {err}")
        return False, err

    xelatex_bin = find_executable("xelatex")
    if not xelatex_bin:
        err = "XeLaTeX was not found. Please install MiKTeX (Windows) or texlive-xetex (Linux)."
        log_func(f"[ERROR] {err}")
        return False, err

    # Resolve output file and allow a custom destination without changing the input.
    if output_file:
        output_file = Path(output_file).resolve()
    else:
        destination = Path(output_directory).expanduser().resolve() if output_directory else OUTPUT_DIR
        name = (output_name or input_path.stem).strip()
        if not name or Path(name).name != name:
            err = "Output filename must be a name, not a path."
            log_func(f"[ERROR] {err}")
            return False, err
        if name.lower().endswith(".pdf"):
            name = name[:-4]
        output_file = destination / f"{name}.pdf"
    output_file = available_output_path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Determine font size
    if custom_font_size:
        fontsize_val = f"{custom_font_size}pt" if not str(custom_font_size).endswith("pt") else str(custom_font_size)
    else:
        fontsize_val = FONT_SIZES.get(font_size_choice, "14pt")
    body_font_points = float(str(fontsize_val).lower().removesuffix("pt"))
    try:
        line_height_value = float(line_height)
    except (TypeError, ValueError):
        line_height_value = 1.1
    line_height_value = min(2.5, max(0.7, line_height_value))
    spacing_value = str(paragraph_spacing).strip() or "6pt"
    if not re.fullmatch(r"\d+(?:\.\d+)?(?:pt|mm|cm|in|em)", spacing_value):
        spacing_value = "6pt"
    toc_title_size = "16pt"

    # Determine geometry
    geom_list = PAGE_SIZES.get(page_size_choice, PAGE_SIZES["A4"]).copy()
    if orientation == "Landscape":
        geom_list.append("landscape")
    if margin_choice == "Custom" and custom_margin:
        margin_value = custom_margin
    elif margin_choice == "Page default":
        margin_value = PAGE_DEFAULT_MARGINS.get(page_size_choice, "1in")
    else:
        margin_value = MARGIN_PRESETS.get(margin_choice, "1in")
    geom_list.append(f"margin={margin_value}")

    source_path = input_path
    temporary_directory = None
    if input_path.suffix.lower() in {".doc", ".mobi"}:
        temporary_directory = tempfile.TemporaryDirectory(prefix="md-to-pdf-")
        temp_dir = Path(temporary_directory.name)
        if input_path.suffix.lower() == ".doc":
            converter_bin = find_executable("soffice") or find_executable("libreoffice")
            converted_path = temp_dir / f"{input_path.stem}.docx"
            adapter_command = [converter_bin, "--headless", "--convert-to", "docx", "--outdir", str(temp_dir), str(input_path)] if converter_bin else None
        else:
            converter_bin = find_executable("ebook-convert")
            converted_path = temp_dir / f"{input_path.stem}.epub"
            adapter_command = [converter_bin, str(input_path), str(converted_path)] if converter_bin else None
        if not adapter_command:
            temporary_directory.cleanup()
            adapter_name = "LibreOffice" if input_path.suffix.lower() == ".doc" else "Calibre (ebook-convert)"
            err = f"{adapter_name} is required to convert {input_path.suffix} files."
            log_func(f"[ERROR] {err}")
            return False, err
        try:
            adapter_result = subprocess.run(adapter_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
            if adapter_result.returncode != 0 or not converted_path.exists():
                err = adapter_result.stderr or f"Could not convert {input_path.suffix} input to an intermediate format."
                log_func(f"[ERROR] {err}")
                return False, err
            source_path = converted_path
        except Exception as e:
            log_func(f"[EXCEPTION] {e}")
            return False, str(e)

    cmd = [
        pandoc_bin,
        str(source_path),
        "-o", str(output_file),
        f"--pdf-engine={xelatex_bin}",
        f"--template={TEMPLATE_PATH}",
        f"--lua-filter={LUA_FILTER_PATH}",
        "--resource-path=" + os.pathsep.join(dict.fromkeys(
            str(path) for path in (source_path.parent, input_path.parent, Path.cwd())
        )),
        "-V", f"fontsize={fontsize_val}"
    ]

    if input_format == "plain":
        # Pandoc has no plain-text reader; escaped Markdown keeps text literal.
        cmd[1:1] = ["--from=markdown+hard_line_breaks"]
    elif input_format:
        cmd[1:1] = [f"--from={input_format}"]
    elif input_path.suffix.lower() in {".md", ".markdown", ".txt"}:
        cmd[1:1] = ["--from=markdown"]

    if include_toc:
        cmd.append("--toc")

    selected_heading_font = resolve_font_file(heading_font, "english")
    heading_latin_font = selected_heading_font if font_file_supports_codepoint(selected_heading_font, 0x0041) else resolve_font_file(english_font, "english")
    heading_bengali_font = selected_heading_font if font_file_supports_codepoint(selected_heading_font, 0x0985) else resolve_font_file(bengali_font, "bengali")
    is_windows = sys.platform.startswith("win")
    bundled_emoji_font = resolve_bundled_font("Segoe UI Emoji", "symbol") if is_windows else resolve_bundled_font("Noto Emoji", "symbol")
    bundled_symbol_font = resolve_bundled_font("Segoe UI Symbol", "symbol") if is_windows else resolve_bundled_font("Noto Sans Symbols 2", "symbol")
    bundled_fonts = {
        "fontenglish": resolve_font_file(english_font, "english"),
        "fontheadinglatin": heading_latin_font,
        "fontheadingbengali": heading_bengali_font,
        "fontbengali": resolve_font_file(bengali_font, "bengali"),
        "fontarabic": resolve_font_file(arabic_font, "arabic"),
        "fontemoji": bundled_emoji_font,
        "fontsymbol": bundled_symbol_font,
        "fontemojiSupplement": resolve_bundled_font("Noto Emoji", "symbol"),
    }
    font_file_vars = {}
    for name, bundled_font in bundled_fonts.items():
        if bundled_font:
            filename, font_path = bundled_font
            font_file_vars[f"{name}file"] = filename
            font_file_vars[f"{name}path"] = font_path
            if name in {"fontenglish", "fontbengali", "fontarabic"}:
                font_file_vars[f"{name}features"] = font_style_features(bundled_font)
    template_vars = {
        "fontenglish": english_font,
        "fontheading": heading_font,
        "fontbengali": bengali_font,
        "fontarabic": arabic_font,
        "fontemoji": "Segoe UI Emoji" if is_windows else "Noto Emoji",
        "fontsymbol": "Segoe UI Symbol" if is_windows else "Noto Sans Symbols 2",
        "fontcurrency": "Segoe UI" if is_windows else english_font,
        "pagenumberstyle": page_number_style,
        "pagenumbertext": {
            "Page 1 of 10": r"Page~\thepage\ of~\pageref*{LastPage}",
            "1 / 10": r"\thepage\ /\ \pageref*{LastPage}",
            "Page 1": r"Page~\thepage",
            "1": r"\thepage",
        }.get(page_number_format, r"Page~\thepage\ of~\pageref*{LastPage}"),
        "pagenumbertextbangla": {
            "Page 1 of 10": r"{\bengalifont পৃষ্ঠা}~{\bangladigits{\getpagerefnumber{LastPage}}}~{\bengalifont এর}~{\bangladigits{\arabic{page}}}",
            "1 / 10": r"{\bangladigits{\getpagerefnumber{LastPage}}}~ / ~{\bangladigits{\arabic{page}}}",
            "Page 1": r"{\bengalifont পৃষ্ঠা}~{\bangladigits{\arabic{page}}}",
            "1": r"{\bangladigits{\arabic{page}}}",
        }.get(page_number_format, r"{\bengalifont পৃষ্ঠা}~{\bangladigits{\getpagerefnumber{LastPage}}}~{\bengalifont এর}~{\bangladigits{\arabic{page}}}"),
        "pagenumberposition": {"Bottom left": "L", "Middle": "C", "Bottom right": "R"}.get(page_number_position, "C"),
        "pagenumbersize": page_number_size,
                "frontpagenumberstyle": front_page_number_style,
                "frontpagenumbertext": {
                    "Page 1 of 10": r"Page~\thepage\ of~\getpagerefnumber{FrontMatterLastPage}",
                    "1 / 10": r"\thepage\ / \getpagerefnumber{FrontMatterLastPage}",
                    "Page 1": r"Page~\thepage",
                    "1": r"\thepage",
                }.get(front_page_number_format, r"\thepage"),
                "frontpagenumbertextbangla": {
                    "Page 1 of 10": r"{\bengalifont পৃষ্ঠা}~{\bangladigits{\getpagerefnumber{FrontMatterLastPage}}}~{\bengalifont এর}~{\bangladigits{\arabic{page}}}",
                    "1 / 10": r"{\bangladigits{\arabic{page}}}~ / ~{\bangladigits{\getpagerefnumber{FrontMatterLastPage}}}",
                    "Page 1": r"{\bengalifont পৃষ্ঠা}~{\bangladigits{\arabic{page}}}",
                    "1": r"{\bangladigits{\arabic{page}}}",
                }.get(front_page_number_format, r"{\bangladigits{\arabic{page}}}"),
                "frontpagenumberposition": {"Bottom left": "L", "Middle": "C", "Bottom right": "R"}.get(front_page_number_position, "C"),
                "frontpagenumbersize": front_page_number_size,
        "indentamount": indent_amount,
        "paragraphspacing": spacing_value,
        "lineheight": f"{line_height_value:g}",
        "toctitlealignment": {"Left": "", "Center": r"\hfill", "Right": r"\hfill"}.get(toc_alignment, r"\hfill"),
        "toctitleendfill": {"Left": r"\hfill", "Center": r"\hfill", "Right": ""}.get(toc_alignment, r"\hfill"),
        "toctitlesize": toc_title_size,
        "toctitlecolor": {"Classic": "blue!65!black", "Minimal": "black", "Decorative": "teal!65!black"}.get(toc_design, "blue!65!black"),
        "tocentrycolor": {"Classic": "blue!55!black", "Minimal": "black", "Decorative": "teal!55!black"}.get(toc_design, "blue!55!black"),
        "tocaftertitle": {
            "Classic": r"\par\medskip\hrule\bigskip",
            "Minimal": r"\par\medskip",
            "Decorative": r"\par\medskip\hrule height 1pt\bigskip",
        }.get(toc_design, r"\par\medskip\hrule\bigskip"),
    }
    template_vars.update({name: value for name, value in font_file_vars.items() if value})
    enabled_template_flags = {
        "pagenumbers": page_numbers,
        "firstlineindent": indent_first_line,
        "centerheadings": center_headings,
        "boldheadings": bold_headings,
        "beautifytoc": beautify_toc,
        "pageborder": page_border,
        "toclanguagebangla": toc_language == "Bangla",
        "pagenumberlanguagebangla": page_number_language == "Bangla",
            "frontpagenumbers": front_page_numbers and include_toc,
            "frontpagenumberlanguagebangla": front_page_number_language == "Bangla",
        "tocpagebangla": toc_language == "Bangla",
        "hyphenation": hyphenation,
        "copyfriendlytext": copy_friendly_text,
    }
    template_vars.update({name: "true" for name, enabled in enabled_template_flags.items() if enabled})
    for name, value in template_vars.items():
        cmd.extend(["-V", f"{name}={value}"])

    for g in geom_list:
        cmd.extend(["-V", f"geometry:{g}"])

    log_func(f"Converting '{input_path.name}' -> '{output_file.name}'...")
    log_func(f"  • Page Size : {page_size_choice} ({', '.join(geom_list)})")
    log_func(f"  • Font Size : {fontsize_val}")
    log_func(f"  • Fonts     : English={english_font}, Bengali={bengali_font}, Arabic={arabic_font}")

    try:
        process_environment = os.environ.copy()
        with tempfile.TemporaryDirectory(prefix="md-to-pdf-images-") as media_directory:
            if input_format == "plain":
                literal_source = Path(media_directory) / f"{source_path.stem}-literal.md"
                literal_source.write_text(
                    escape_plain_text(source_path.read_text(encoding="utf-8-sig")),
                    encoding="utf-8",
                )
                cmd[cmd.index(str(source_path))] = str(literal_source)
            else:
                prepared_source = prepare_remote_images(source_path, pandoc_bin, media_directory, log_func)
                if prepared_source != source_path:
                    cmd[cmd.index(str(source_path))] = str(prepared_source)
                    for index, argument in enumerate(cmd):
                        if argument.startswith("--from="):
                            cmd[index] = "--from=json"
                            break
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=process_environment)
        if proc.returncode == 0:
            warning_continuation = False
            for line in proc.stderr.splitlines():
                if line.startswith("[WARNING]"):
                    log_func(line)
                    warning_continuation = True
                elif warning_continuation and (line[:1].isspace() or line == "  }"):
                    log_func(f"  {line.strip()}")
                else:
                    warning_continuation = False
            log_func(f"[SUCCESS] PDF successfully created: {output_file}")
            return True, str(output_file)
        else:
            log_func(f"[ERROR] Pandoc/XeLaTeX conversion failed (Code {proc.returncode}):")
            if proc.stderr:
                for line in proc.stderr.strip().splitlines()[-10:]:
                    log_func(f"  {line}")
            return False, proc.stderr
    except Exception as e:
        log_func(f"[EXCEPTION] {e}")
        return False, str(e)
    finally:
        if temporary_directory:
            temporary_directory.cleanup()


def convert_many_to_pdf(input_files, log_func=print, output_name=None, **options):
    """Convert multiple sources with shared settings, returning per-file results."""
    results = []
    for source in input_files:
        file_options = dict(options)
        file_output_name = output_name if len(input_files) == 1 else None
        results.append((source, *convert_md_to_pdf(source, output_name=file_output_name, log_func=log_func, **file_options)))
    return results


def open_in_system(path):
    """Open a file or folder in the default OS application."""
    target = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(target)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def prompt_post_conversion_menu(succeeded, output_directory=None):
    """Show follow-up actions after a successful conversion in CLI mode."""
    print("\nWhat would you like to do next?")
    print("  1. Open Converted File")
    print("  2. Open Output Folder")
    print("  3. Convert Another file")
    print("  4. Exit")

    while True:
        choice = input("Select [1-4]: ").strip()
        if choice == "1":
            if not succeeded:
                print("[INFO] No converted file is available to open.")
                return "exit"
            file_to_open = str(Path(succeeded[0]))
            print(f"Opening converted file: {file_to_open}")
            open_in_system(file_to_open)
            return "open-file"
        if choice == "2":
            folder_path = str(Path(output_directory)) if output_directory else str(OUTPUT_DIR)
            print(f"Opening output folder: {folder_path}")
            open_in_system(folder_path)
            return "open-output"
        if choice == "3":
            return "convert-another"
        if choice == "4":
            return "exit"
        print("Invalid selection. Please choose a number from 1 to 4.")


def load_profiles():
    """Load built-in presets and saved profiles, preserving all saved customization."""
    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
            saved_profiles = json.load(profile_file)
        if not isinstance(saved_profiles, dict):
            saved_profiles = {}
    except (OSError, json.JSONDecodeError):
        saved_profiles = {}

    profiles = {
        name: {**PROFILE_BASE_SETTINGS, **settings}
        for name, settings in BUILT_IN_PROFILES.items()
    }
    for name, settings in saved_profiles.items():
        if isinstance(settings, dict) and name not in BUILT_IN_PROFILES:
            profiles[name] = {**PROFILE_BASE_SETTINGS, **settings}
    return profiles


def save_profile(name, settings):
    """Persist one named conversion profile."""
    if name in BUILT_IN_PROFILES or name == LAST_USED_PROFILE:
        raise ValueError("Built-in and internal profiles cannot be overwritten.")
    profiles = load_profiles()
    profiles[name] = settings
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_PATH.open("w", encoding="utf-8") as profile_file:
        json.dump(profiles, profile_file, ensure_ascii=False, indent=2)


def save_last_used_settings(settings):
    """Persist the most recent GUI configuration for the next application launch."""
    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
            saved_profiles = json.load(profile_file)
        if not isinstance(saved_profiles, dict):
            saved_profiles = {}
    except (OSError, json.JSONDecodeError):
        saved_profiles = {}
    saved_profiles[LAST_USED_PROFILE] = settings
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_PATH.open("w", encoding="utf-8") as profile_file:
        json.dump(saved_profiles, profile_file, ensure_ascii=False, indent=2)


def delete_profile(name):
    """Delete a user-created profile without changing built-in presets."""
    if name in BUILT_IN_PROFILES or name == LAST_USED_PROFILE:
        raise ValueError("Built-in and internal profiles cannot be deleted.")
    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
            saved_profiles = json.load(profile_file)
    except (OSError, json.JSONDecodeError):
        return False
    if name not in saved_profiles:
        return False
    del saved_profiles[name]
    with PROFILE_PATH.open("w", encoding="utf-8") as profile_file:
        json.dump(saved_profiles, profile_file, ensure_ascii=False, indent=2)
    return True


# ==========================================
# Terminal / CLI Interactive Wizard
# ==========================================
def cli_interactive_flow(auto_mode=False):
    """Interactive command-line flow with user prompts."""
    while True:
        print("=" * 55)
        print(" Multilingual Markdown to PDF Converter")
        print(" Support: Bengali (SolaimanLipi), Arabic (Amiri), Symbols")
        print("=" * 55)

        # 1. Select Input File
        md_files = sorted(path for path in INPUT_DIR.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS) if INPUT_DIR.exists() else []
        input_files = []

        print("\n[Step 1] Select Input File:")
        if md_files:
            for idx, f in enumerate(md_files, 1):
                print(f"  {idx}. {f.name}")
            print("  A. Convert all listed files")
            print("  0. Enter custom path(s), separated by semicolons")

            while True:
                choice = input(f"Choose file [1-{len(md_files)}, A, 0] (default 1): ").strip()
                if not choice:
                    input_files = [str(md_files[0])]
                    break
                elif choice == "0":
                    paths = [part.strip().strip('"') for part in input("Enter supported file path(s), separated by semicolons: ").split(";") if part.strip()]
                    if paths and all(Path(path).is_file() and Path(path).suffix.lower() in SUPPORTED_INPUT_EXTENSIONS for path in paths):
                        input_files = paths
                        break
                    print("File not found! Try again.")
                elif choice.lower() == "a":
                    input_files = [str(path) for path in md_files]
                    break
                elif choice.isdigit() and 1 <= int(choice) <= len(md_files):
                    input_files = [str(md_files[int(choice) - 1])]
                    break
                else:
                    print("Invalid selection.")
        else:
            while True:
                paths = [part.strip().strip('"') for part in input("Enter supported file path(s), separated by semicolons: ").split(";") if part.strip()]
                if paths and all(Path(path).is_file() and Path(path).suffix.lower() in SUPPORTED_INPUT_EXTENSIONS for path in paths):
                    input_files = paths
                    break
                print("File not found! Try again.")

        input_file = input_files[0]
        print(f"--> Selected {len(input_files)} file(s): {', '.join(Path(path).name for path in input_files)}")
        if auto_mode and len(input_files) > 1:
            print("[ERROR] Auto-convert supports one input document at a time.")
            return

        # 2. Select Page Size and margins
        print("\n[Step 2] Select Page Size:")
        print("  1. A4  2. Letter  3. A5  4. Legal  5. For Mobile  6. For PC")
        size_map = {"1": "A4", "2": "Letter", "3": "A5", "4": "Legal", "5": "For Mobile", "6": "For PC"}
        size_choice = input("Choose Page Size [1-6] (default 1): ").strip()
        selected_page_size = size_map.get(size_choice, "A4")
        print(f"--> Selected: {selected_page_size}")
        orientation_choice = input("Page orientation [Portrait/Landscape] (default Portrait): ").strip().lower()
        orientation = "Landscape" if orientation_choice.startswith("l") else "Portrait"

        print("\n[Step 3] Select Margins:")
        margin_names = ["Page default", *MARGIN_PRESETS]
        for idx, name in enumerate(margin_names, 1):
            print(f"  {idx}. {name}")
        print(f"  {len(margin_names) + 1}. Custom")
        margin_choice_input = input(f"Choose margins [1-{len(margin_names) + 1}] (default 1): ").strip() or "1"
        margin_choice = margin_names[int(margin_choice_input) - 1] if margin_choice_input.isdigit() and 1 <= int(margin_choice_input) <= len(margin_names) else "Page default"
        custom_margin = None
        if margin_choice_input == str(len(margin_names) + 1):
            margin_choice = "Custom"
            custom_margin = input("Enter custom margin (e.g. 25mm, 0.8in): ").strip() or "1in"

        # 4. Select Font Size
        print("\n[Step 4] Select Font Size:")
        print("  1. Standard (11pt)")
        print("  2. Medium (14pt)")
        print("  3. Large (17pt)")
        print("  4. Custom Font Size (specify in points)")
        font_map = {"1": "Standard", "2": "Medium", "3": "Large"}
        font_choice = input("Choose Font Size [1-4] (default 2): ").strip()

        custom_font_size = None
        if font_choice == "4":
            while True:
                custom_val = input("Enter custom font size (e.g. 8 to 24): ").strip()
                if custom_val.isdigit() and 6 <= int(custom_val) <= 36:
                    custom_font_size = int(custom_val)
                    selected_font_size = f"Custom ({custom_font_size}pt)"
                    break
                print("Please enter a valid number between 6 and 36.")
        else:
            selected_font_size = font_map.get(font_choice, "Medium")
        print(f"--> Selected: {selected_font_size}")

        print("\n[Step 5] Select Language Fonts (press Enter to keep defaults):")
        english_font = input("English font [DejaVu Sans]: ").strip() or "DejaVu Sans"
        heading_font = input(f"Heading font [{english_font}]: ").strip() or english_font
        bengali_font = input("Bengali font [SolaimanLipi]: ").strip() or "SolaimanLipi"
        arabic_font = input("Arabic font [Amiri]: ").strip() or "Amiri"

        def ask_yes_no(prompt, default):
            answer = input(f"{prompt} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
            return default if not answer else answer in ("y", "yes")

        include_toc = ask_yes_no("Include Table of Contents", True)
        beautify_toc = ask_yes_no("Beautify Table of Contents", True) if include_toc else False
        toc_language = "Bangla" if include_toc and input("TOC language 1) English  2) Bangla (default 1): ").strip() == "2" else "English"
        page_numbers = ask_yes_no("Show page numbers", False)
        page_number_language = "English"
        if page_numbers and input("Page-number language 1) English  2) Bangla (default 1): ").strip() == "2":
            page_number_language = "Bangla"
        page_border = ask_yes_no("Add decorative page border", False)
        hyphenation = ask_yes_no("Enable hyphenation", True)
        copy_friendly_text = ask_yes_no("Improve copied text for script fonts", False)
        line_height = input("Line height multiplier [1.1] (e.g. 1.0-1.8): ").strip() or "1.1"
        spacing_choice = input("Paragraph spacing 1) None  2) Compact 3pt  3) Normal 6pt  4) Relaxed 9pt  5) Custom (default 3): ").strip() or "3"
        paragraph_spacing = {"1": "0pt", "2": "3pt", "3": "6pt", "4": "9pt"}.get(spacing_choice)
        if spacing_choice == "5":
            paragraph_spacing = input("Custom paragraph spacing (e.g. 8pt, 2mm): ").strip() or "6pt"
        elif paragraph_spacing is None:
            paragraph_spacing = "6pt"
        toc_alignments = {"1": "Left", "2": "Center", "3": "Right"}
        toc_alignment = toc_alignments.get(input("TOC title alignment 1) Left  2) Center  3) Right (default 2): ").strip(), "Center")
        toc_designs = {"1": "Classic", "2": "Minimal", "3": "Decorative"}
        toc_design = toc_designs.get(input("TOC design 1) Classic  2) Minimal  3) Decorative (default 1): ").strip(), "Classic")
        page_number_style = "arabic"
        page_number_format = "Page 1 of 10"
        page_number_position = "Middle"
        page_number_size = "9pt"
        if page_numbers:
            style_input = input("Page number style [arabic/roman/Roman] (default arabic): ").strip()
            page_number_style = style_input if style_input in ("arabic", "roman", "Roman") else "arabic"
            formats = {"1": "Page 1 of 10", "2": "1 / 10", "3": "Page 1", "4": "1"}
            format_choice = input("Page format 1) Page 1 of 10  2) 1 / 10  3) Page 1  4) 1 (default 1): ").strip()
            page_number_format = formats.get(format_choice, "Page 1 of 10")
            positions = {"1": "Bottom left", "2": "Middle", "3": "Bottom right"}
            page_number_position = positions.get(input("Position 1) Bottom left  2) Middle  3) Bottom right (default 2): ").strip(), "Middle")
            page_number_size = input("Page number text size in points [9pt]: ").strip() or "9pt"
        front_page_numbers = ask_yes_no("Number TOC/front-matter pages", False) if include_toc else False
        front_page_number_style = "roman"
        front_page_number_format = "1"
        front_page_number_position = "Middle"
        front_page_number_size = "9pt"
        front_page_number_language = "English"
        if front_page_numbers:
            front_style = input("Front-page style [roman/Roman/arabic] (default roman): ").strip()
            front_page_number_style = front_style if front_style in ("roman", "Roman", "arabic") else "roman"
            front_formats = {"1": "Page 1 of 10", "2": "1 / 10", "3": "Page 1", "4": "1"}
            front_format = input("Front-page format 1) Page 1 of 10  2) 1 / 10  3) Page 1  4) 1 (default 4): ").strip() or "4"
            front_page_number_format = front_formats.get(front_format, "1")
            positions = {"1": "Bottom left", "2": "Middle", "3": "Bottom right"}
            front_position = input("Front-page position 1) Bottom left  2) Middle  3) Bottom right (default 2): ").strip()
            front_page_number_position = positions.get(front_position, "Middle")
            front_page_number_size = input("Front-page number size in points [9pt]: ").strip() or "9pt"
            if input("Front-page number language 1) English  2) Bangla (default 1): ").strip() == "2":
                front_page_number_language = "Bangla"
        indent_first_line = ask_yes_no("Indent first line of paragraphs", False)
        indent_amount = "0.25in"
        if indent_first_line:
            indent_amount = input("First-line indent amount [0.25in]: ").strip() or indent_amount
        center_headings = ask_yes_no("Center headings", True)
        bold_headings = ask_yes_no("Make headings bold", True)
        output_name = input("Custom output filename (single file only; blank keeps source name): ").strip() or None
        if len(input_files) > 1 and output_name:
            print("Batch mode uses each input's filename; ignoring the custom output filename.")
            output_name = None
        output_directory = input(f"Output folder [{OUTPUT_DIR}]: ").strip().strip('"') or str(OUTPUT_DIR)

        # Auto-convert mode vs One-time conversion
        if auto_mode:
            print("\n[Step 6] Auto-Convert Settings:")
            interval_input = input("Enter check interval in seconds (default 2): ").strip()
            interval = int(interval_input) if interval_input.isdigit() and int(interval_input) > 0 else 2

            print(f"\n[STARTING] Watching '{Path(input_file).name}' for changes every {interval}s...")
            print("Press Ctrl+C to stop.\n")

            # Initial conversion
            conversion_options = dict(english_font=english_font, heading_font=heading_font, bengali_font=bengali_font, arabic_font=arabic_font, margin_choice=margin_choice, custom_margin=custom_margin, orientation=orientation, page_numbers=page_numbers, page_number_style=page_number_style, page_number_format=page_number_format, page_number_position=page_number_position, page_number_size=page_number_size, page_number_language=page_number_language, front_page_numbers=front_page_numbers, front_page_number_style=front_page_number_style, front_page_number_format=front_page_number_format, front_page_number_position=front_page_number_position, front_page_number_size=front_page_number_size, front_page_number_language=front_page_number_language, indent_first_line=indent_first_line, indent_amount=indent_amount, paragraph_spacing=paragraph_spacing, center_headings=center_headings, bold_headings=bold_headings, include_toc=include_toc, beautify_toc=beautify_toc, toc_language=toc_language, page_border=page_border, toc_alignment=toc_alignment, toc_design=toc_design, hyphenation=hyphenation, line_height=line_height, copy_friendly_text=copy_friendly_text, output_directory=output_directory, output_name=output_name)
            convert_md_to_pdf(input_file, selected_page_size, selected_font_size, custom_font_size, **conversion_options)

            last_mtime = Path(input_file).stat().st_mtime
            try:
                while True:
                    time.sleep(interval)
                    current_mtime = Path(input_file).stat().st_mtime
                    if current_mtime != last_mtime:
                        last_mtime = current_mtime
                        print(f"\n[CHANGE DETECTED] File updated at {time.strftime('%H:%M:%S')}. Re-converting...")
                        convert_md_to_pdf(input_file, selected_page_size, selected_font_size, custom_font_size, **conversion_options)
            except KeyboardInterrupt:
                print("\nAuto-convert stopped by user.")
        else:
            print("\n[Step 6] Starting PDF Conversion...")
            results = convert_many_to_pdf(input_files, page_size_choice=selected_page_size, font_size_choice=selected_font_size, custom_font_size=custom_font_size, output_name=output_name, english_font=english_font, heading_font=heading_font, bengali_font=bengali_font, arabic_font=arabic_font, margin_choice=margin_choice, custom_margin=custom_margin, orientation=orientation, page_numbers=page_numbers, page_number_style=page_number_style, page_number_format=page_number_format, page_number_position=page_number_position, page_number_size=page_number_size, page_number_language=page_number_language, front_page_numbers=front_page_numbers, front_page_number_style=front_page_number_style, front_page_number_format=front_page_number_format, front_page_number_position=front_page_number_position, front_page_number_size=front_page_number_size, front_page_number_language=front_page_number_language, indent_first_line=indent_first_line, indent_amount=indent_amount, paragraph_spacing=paragraph_spacing, center_headings=center_headings, bold_headings=bold_headings, include_toc=include_toc, beautify_toc=beautify_toc, toc_language=toc_language, page_border=page_border, toc_alignment=toc_alignment, toc_design=toc_design, hyphenation=hyphenation, line_height=line_height, copy_friendly_text=copy_friendly_text, output_directory=output_directory)
            succeeded = [result for _source, success, result in results if success]
            failed = [(source, result) for source, success, result in results if not success]
            print(f"\nFinished: {len(succeeded)} of {len(results)} files converted.")
            for path in succeeded:
                print(f"  PDF: {path}")
            for source, error in failed:
                print(f"  Failed: {Path(source).name}: {error}")

            action = prompt_post_conversion_menu(succeeded, output_directory)
            if action == "convert-another":
                continue
            if action in {"open-file", "open-output"}:
                continue
            return


# ==========================================
# Graphical User Interface (Flet & Tkinter fallback)
# font_picker = ttk.Combobox(typography_tab
# ==========================================
def launch_gui(auto_mode_init=False, force_legacy=False):
    """Launch the GUI — defaults to modern Flet Material 3 UI with Tkinter fallback."""
    if force_legacy or "--legacy-gui" in sys.argv:
        from src.ui.legacy_tkinter import launch_gui as launch_legacy_gui
        return launch_legacy_gui(auto_mode_init=auto_mode_init)

    try:
        from src.ui.flet_app import launch_flet_app
        return launch_flet_app()
    except Exception as e:
        print(f"[INFO] Launching legacy desktop interface (Flet: {e})")
        from src.ui.legacy_tkinter import launch_gui as launch_legacy_gui
        return launch_legacy_gui(auto_mode_init=auto_mode_init)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        cli_interactive_flow(auto_mode="--auto" in sys.argv)
    elif "--auto" in sys.argv:
        launch_gui(auto_mode_init=True)
    else:
        launch_gui(auto_mode_init=False)
