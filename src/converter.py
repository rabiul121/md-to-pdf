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
    "English": ["DejaVu Sans", "Noto Sans", "Noto Serif", "Source Serif 4", "Inter", "JetBrains Mono"],
    "Bengali": ["SolaimanLipi", "Noto Sans Bengali", "Noto Serif Bengali", "Kalpurush", "Ekushey Lalsalu"],
    "Arabic": ["Amiri", "Noto Naskh Arabic", "Noto Sans Arabic", "Scheherazade New"],
}

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
    "Minimal": {"toc_design": "Minimal", "beautify_toc": False, "page_border": False},
    "Decorative": {"toc_design": "Decorative", "beautify_toc": True, "page_border": True},
}

BUNDLED_FONT_FILES = {
    "english": {
        "DejaVu Sans": "DejaVuSans.ttf",
        "Noto Sans": "NotoSans-VariableFont_wdth,wght.ttf",
        "Noto Serif": "NotoSerif-VariableFont_wdth,wght.ttf",
        "Source Serif 4": "SourceSerif4-VariableFont_opsz,wght.ttf",
        "Inter": "Inter-VariableFont_opsz,wght.ttf",
        "JetBrains Mono": "JetBrainsMono-VariableFont_wght.ttf",
    },
    "bengali": {
        "SolaimanLipi": "SolaimanLipi.ttf",
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

def convert_md_to_pdf(input_file, page_size_choice="A4", font_size_choice="Medium", custom_font_size=None, output_file=None, log_func=print, english_font="DejaVu Sans", bengali_font="SolaimanLipi", arabic_font="Amiri", margin_choice="Page default", custom_margin=None, orientation="Portrait", page_numbers=False, page_number_style="arabic", page_number_format="Page 1 of 10", page_number_position="Middle", page_number_size="9pt", front_page_numbers=False, front_page_number_style="roman", front_page_number_format="1", front_page_number_position="Middle", front_page_number_size="9pt", front_page_number_language="English", indent_first_line=False, indent_amount="0.25in", center_headings=True, bold_headings=True, include_toc=True, beautify_toc=True, output_name=None, output_directory=None, toc_language="English", page_number_language="English", page_border=False, toc_alignment="Center", toc_design="Classic", heading_font="DejaVu Sans", hyphenation=True, line_height="1.1", paragraph_spacing="6pt", copy_friendly_text=False):
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
        "-V", f"fontsize={fontsize_val}"
    ]

    if input_path.suffix.lower() in {".md", ".markdown", ".txt"}:
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
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=process_environment)
        if proc.returncode == 0:
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
# Graphical User Interface (Tkinter)
# ==========================================
def launch_gui(auto_mode_init=False):
    """Launch the modern desktop UI window."""
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except ImportError:
        print("[WARNING] Tkinter not available, falling back to CLI interface.")
        cli_interactive_flow(auto_mode=auto_mode_init)
        return

    root = tk.Tk()
    root.title("Markdown to PDF Converter (Multilingual)")
    root.geometry("760x850")
    root.minsize(640, 600)

    # Style
    style = ttk.Style(root)
    available_themes = style.theme_names()
    if "clam" in available_themes:
        style.theme_use("clam")

    # Variables
    input_file_var = tk.StringVar()
    output_name_var = tk.StringVar()
    output_directory_var = tk.StringVar(value=str(OUTPUT_DIR))
    toc_language_var = tk.StringVar(value="English")
    toc_alignment_var = tk.StringVar(value="Center")
    toc_design_var = tk.StringVar(value="Classic")
    page_number_language_var = tk.StringVar(value="English")
    page_border_var = tk.BooleanVar(value=False)
    theme_var = tk.StringVar(value="Light")
    page_size_var = tk.StringVar(value="A4")
    orientation_var = tk.StringVar(value="Portrait")
    margin_var = tk.StringVar(value="Page default")
    custom_margin_var = tk.StringVar(value="25mm")
    font_size_var = tk.StringVar(value="Medium")
    custom_font_size_var = tk.IntVar(value=14)
    english_font_var = tk.StringVar(value="DejaVu Sans")
    heading_font_var = tk.StringVar(value="DejaVu Sans")
    bengali_font_var = tk.StringVar(value="SolaimanLipi")
    arabic_font_var = tk.StringVar(value="Amiri")
    hyphenation_var = tk.BooleanVar(value=True)
    copy_friendly_text_var = tk.BooleanVar(value=False)
    line_height_var = tk.StringVar(value="1.1")
    page_numbers_var = tk.BooleanVar(value=False)
    page_number_style_var = tk.StringVar(value="arabic")
    page_number_format_var = tk.StringVar(value="Page 1 of 10")
    page_number_position_var = tk.StringVar(value="Middle")
    page_number_size_var = tk.StringVar(value="9pt")
    front_page_numbers_var = tk.BooleanVar(value=False)
    front_page_number_style_var = tk.StringVar(value="roman")
    front_page_number_format_var = tk.StringVar(value="1")
    front_page_number_position_var = tk.StringVar(value="Middle")
    front_page_number_size_var = tk.StringVar(value="9pt")
    front_page_number_language_var = tk.StringVar(value="English")
    indent_first_line_var = tk.BooleanVar(value=False)
    indent_amount_var = tk.StringVar(value="0.25in")
    paragraph_spacing_var = tk.StringVar(value="6pt")
    custom_paragraph_spacing_var = tk.StringVar(value="6pt")
    center_headings_var = tk.BooleanVar(value=True)
    bold_headings_var = tk.BooleanVar(value=True)
    include_toc_var = tk.BooleanVar(value=True)
    beautify_toc_var = tk.BooleanVar(value=True)
    mode_var = tk.StringVar(value="auto" if auto_mode_init else "once")
    interval_var = tk.IntVar(value=2)
    status_var = tk.StringVar(value="Ready. Select an input file to begin.")
    is_watching = [False]
    watch_thread = [None]
    selected_files = []

    # Pre-select first markdown file in directory
    md_files = sorted(path for path in INPUT_DIR.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS) if INPUT_DIR.exists() else []
    if md_files:
        input_file_var.set(str(md_files[0]))

    palette = {}

    def apply_theme(_event=None):
        palette.update({
            "Light": {"background": "#f3f5f7", "surface": "#ffffff", "foreground": "#1e2933", "muted": "#66727e", "accent": "#147d78", "input": "#ffffff", "log": "#17212b", "log_text": "#edf2f7"},
            "Dark": {"background": "#171c22", "surface": "#222a32", "foreground": "#e8edf2", "muted": "#a4b0bb", "accent": "#69c6bb", "input": "#303a44", "log": "#11161b", "log_text": "#e8edf2"},
        }[theme_var.get()])
        colors = palette
        root.configure(bg=colors["background"])
        style.configure("TFrame", background=colors["background"])
        style.configure("Card.TFrame", background=colors["surface"], relief="groove")
        style.configure("TLabel", background=colors["background"], foreground=colors["foreground"], font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=colors["surface"], foreground=colors["foreground"], font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=colors["background"], foreground=colors["foreground"], font=("Segoe UI", 14, "bold"))
        style.configure("Subheader.TLabel", background=colors["background"], foreground=colors["muted"], font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=colors["background"], foreground=colors["muted"], font=("Segoe UI", 9, "italic"))
        style.configure("Section.TLabel", background=colors["surface"], foreground=colors["accent"], font=("Segoe UI", 11, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), background=colors["accent"], foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", colors["accent"])])
        style.configure("TCheckbutton", background=colors["surface"], foreground=colors["foreground"])
        style.map("TCheckbutton", background=[("active", colors["surface"])], foreground=[("disabled", colors["muted"])])
        style.configure("TRadiobutton", background=colors["surface"], foreground=colors["foreground"])
        style.map("TRadiobutton", background=[("active", colors["surface"])], foreground=[("disabled", colors["muted"])])
        style.configure("TEntry", fieldbackground=colors["input"], foreground=colors["foreground"])
        style.configure("TCombobox", fieldbackground=colors["input"], foreground=colors["foreground"])
        content_canvas.configure(bg=colors["background"])
        try:
            log_text.configure(bg=colors["log"], fg=colors["log_text"], insertbackground=colors["log_text"])
        except NameError:
            pass

    # Main Container
    scroll_container = ttk.Frame(root)
    scroll_container.pack(fill=tk.BOTH, expand=True)
    content_canvas = tk.Canvas(scroll_container, bg="#f3f5f7", highlightthickness=0)
    content_scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=content_canvas.yview)
    content_canvas.configure(yscrollcommand=content_scrollbar.set)
    content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    main_frame = ttk.Frame(content_canvas, padding=20)
    canvas_window = content_canvas.create_window((0, 0), window=main_frame, anchor="nw")
    main_frame.bind("<Configure>", lambda _event: content_canvas.configure(scrollregion=content_canvas.bbox("all")))
    content_canvas.bind("<Configure>", lambda event: content_canvas.itemconfigure(canvas_window, width=event.width))

    def scroll_settings_canvas(event):
        widget = event.widget
        widget_path = str(widget)
        if isinstance(widget, str):
            try:
                widget = root.nametowidget(widget)
            except KeyError:
                widget = None
        try:
            widget_class = widget.winfo_class() if widget is not None else ""
        except (AttributeError, tk.TclError):
            widget_class = ""
        if widget_class in {"TCombobox", "Listbox"} or ".popdown" in widget_path:
            return "break"
        content_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    content_canvas.bind_all("<MouseWheel>", scroll_settings_canvas)

    # Title & Description
    title_row = ttk.Frame(main_frame)
    title_row.pack(fill=tk.X)
    ttk.Label(title_row, text="📄 Markdown to PDF Converter", style="Header.TLabel").pack(side=tk.LEFT, anchor="w")
    ttk.Label(title_row, text="Theme", style="TLabel").pack(side=tk.RIGHT, padx=(8, 5))
    theme_picker = ttk.Combobox(title_row, textvariable=theme_var, values=["Light", "Dark"], state="readonly", width=8)
    theme_picker.pack(side=tk.RIGHT)
    theme_picker.bind("<<ComboboxSelected>>", apply_theme)
    ttk.Label(main_frame, text="Bengali (SolaimanLipi) • Arabic (Amiri) • English • Icons/Emoji", style="Subheader.TLabel").pack(anchor="w", pady=(0, 15))

    # --- Section 1: Input File ---
    file_card = ttk.Frame(main_frame, style="Card.TFrame", padding=12)
    file_card.pack(fill=tk.X, pady=(0, 12))
    ttk.Label(file_card, text="1. Select Input File", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

    file_row = ttk.Frame(file_card, style="Card.TFrame")
    file_row.pack(fill=tk.X)
    file_entry = ttk.Entry(file_row, textvariable=input_file_var, font=("Segoe UI", 9))
    file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

    def browse_file():
        chosen = filedialog.askopenfilename(
            title="Select document",
            filetypes=[("Supported documents", "*.md *.markdown *.txt *.doc *.docx *.epub *.mobi"), ("All files", "*.*")],
            initialdir=str(INPUT_DIR)
        )
        if chosen:
            selected_files[:] = [chosen]
            input_file_var.set(chosen)

    def browse_batch():
        chosen = filedialog.askopenfilenames(
            title="Select documents for batch conversion",
            filetypes=[("Supported documents", "*.md *.markdown *.txt *.doc *.docx *.epub *.mobi"), ("All files", "*.*")],
            initialdir=str(INPUT_DIR)
        )
        if chosen:
            selected_files[:] = list(chosen)
            input_file_var.set(f"{len(chosen)} files selected")

    ttk.Button(file_row, text="Browse...", command=browse_file).pack(side=tk.RIGHT)
    ttk.Button(file_row, text="Batch...", command=browse_batch).pack(side=tk.RIGHT, padx=(0, 6))

    output_row = ttk.Frame(file_card, style="Card.TFrame")
    output_row.pack(fill=tk.X, pady=(8, 0))
    ttk.Label(output_row, text="Output name", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Entry(output_row, textvariable=output_name_var, width=22).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
    ttk.Label(output_row, text="Output folder", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Entry(output_row, textvariable=output_directory_var, width=28).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

    def browse_output_directory():
        chosen = filedialog.askdirectory(title="Select output folder", initialdir=output_directory_var.get() or str(OUTPUT_DIR))
        if chosen:
            output_directory_var.set(chosen)

    ttk.Button(output_row, text="Choose...", command=browse_output_directory).pack(side=tk.RIGHT)

    # Quick selector buttons for files in project
    if md_files:
        quick_frame = ttk.Frame(file_card, style="Card.TFrame")
        quick_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(quick_frame, text="Found in project: ", style="Card.TLabel").pack(side=tk.LEFT)
        for f in md_files[:4]:
            def select_quick_file(path=str(f)):
                selected_files[:] = [path]
                input_file_var.set(path)

            btn = ttk.Button(quick_frame, text=f.name, command=select_quick_file)
            btn.pack(side=tk.LEFT, padx=3)

    # --- Section 2: Page Size ---
    page_card = ttk.Frame(main_frame, style="Card.TFrame", padding=12)
    page_card.pack(fill=tk.X, pady=(0, 12))
    ttk.Label(page_card, text="2. Select Page Size", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

    page_opts_frame = ttk.Frame(page_card, style="Card.TFrame")
    page_opts_frame.pack(fill=tk.X)

    page_row = ttk.Frame(page_opts_frame, style="Card.TFrame")
    page_row.pack(fill=tk.X)
    ttk.Label(page_row, text="Paper", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Combobox(page_row, textvariable=page_size_var, values=list(PAGE_SIZES), state="readonly", width=16).pack(side=tk.LEFT, padx=(0, 16))
    ttk.Label(page_row, text="Margins", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Combobox(page_row, textvariable=margin_var, values=["Page default", *MARGIN_PRESETS, "Custom"], state="readonly", width=19).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Entry(page_row, textvariable=custom_margin_var, width=9).pack(side=tk.LEFT)
    ttk.Label(page_row, text="(custom)", style="Card.TLabel").pack(side=tk.LEFT, padx=(4, 0))
    orientation_row = ttk.Frame(page_opts_frame, style="Card.TFrame")
    orientation_row.pack(fill=tk.X, pady=(8, 0))
    ttk.Label(orientation_row, text="Orientation", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 8))
    ttk.Combobox(orientation_row, textvariable=orientation_var, values=["Portrait", "Landscape"], state="readonly", width=14).pack(side=tk.LEFT)

    # --- Section 3: Font Size ---
    font_card = ttk.Frame(main_frame, style="Card.TFrame", padding=12)
    font_card.pack(fill=tk.X, pady=(0, 12))
    ttk.Label(font_card, text="3. Select Font Size", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

    font_row = ttk.Frame(font_card, style="Card.TFrame")
    font_row.pack(fill=tk.X)

    ttk.Radiobutton(font_row, text="Standard (11pt)", variable=font_size_var, value="Standard").pack(side=tk.LEFT, padx=(0, 15))
    ttk.Radiobutton(font_row, text="Medium (14pt)", variable=font_size_var, value="Medium").pack(side=tk.LEFT, padx=(0, 15))
    ttk.Radiobutton(font_row, text="Large (17pt)", variable=font_size_var, value="Large").pack(side=tk.LEFT, padx=(0, 15))
    ttk.Radiobutton(font_row, text="Custom", variable=font_size_var, value="Custom").pack(side=tk.LEFT, padx=(0, 5))

    spin_box = ttk.Spinbox(font_row, from_=8, to=36, textvariable=custom_font_size_var, width=4)
    spin_box.pack(side=tk.LEFT)
    ttk.Label(font_row, text="pt", style="Card.TLabel").pack(side=tk.LEFT, padx=(2, 0))

    # --- Section 4: Typography, contents, and saved profiles ---
    layout_card = ttk.Frame(main_frame, style="Card.TFrame", padding=12)
    layout_card.pack(fill=tk.X, pady=(0, 12))
    ttk.Label(layout_card, text="4. Typography and Document Layout", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
    settings_tabs = ttk.Notebook(layout_card)
    settings_tabs.pack(fill=tk.X, expand=True)
    typography_tab = ttk.Frame(settings_tabs, padding=10)
    contents_tab = ttk.Frame(settings_tabs, padding=10)
    profiles_tab = ttk.Frame(settings_tabs, padding=10)
    settings_tabs.add(typography_tab, text="Typography")
    settings_tabs.add(contents_tab, text="TOC & Page Numbers")
    settings_tabs.add(profiles_tab, text="Profiles")

    font_variables = {
        "English": english_font_var,
        "Headings": heading_font_var,
        "Bengali": bengali_font_var,
        "Arabic": arabic_font_var,
    }
    for row, (label, variable) in enumerate(font_variables.items()):
        bundled_fonts = PROJECT_FONT_CHOICES.get(label, PROJECT_FONT_CHOICES["English"])
        all_fonts = get_font_families(root, bundled_fonts)
        ttk.Label(typography_tab, text=f"{label} font", style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        font_picker = ttk.Combobox(typography_tab, textvariable=variable, values=all_fonts, width=42)
        font_picker.grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)

        def filter_font_list(_event=None, picker=font_picker, selected_font=variable, fonts=all_fonts):
            query = selected_font.get().strip()
            picker.configure(values=filter_font_families(query, fonts) if query else fonts)

        def reset_font_list(_event=None, picker=font_picker, selected_font=variable, fonts=all_fonts):
            if not selected_font.get().strip():
                picker.configure(values=fonts)

        def dismiss_font_dropdown(_event=None, picker=font_picker):
            try:
                picker.tk.call("ttk::combobox::Unpost", str(picker))
            except tk.TclError:
                pass
            return "break"

        font_picker.bind("<KeyRelease>", filter_font_list)
        font_picker.bind("<FocusIn>", reset_font_list)
        font_picker.bind("<Escape>", dismiss_font_dropdown)

    typography_tab.columnconfigure(1, weight=1)
    typography_tab.columnconfigure(2, weight=2)
    layout_controls = ttk.Frame(typography_tab)
    layout_controls.grid(row=len(font_variables), column=0, columnspan=3, sticky="ew", pady=(10, 0))
    ttk.Checkbutton(layout_controls, text="Bold headings", variable=bold_headings_var).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=3)
    ttk.Checkbutton(layout_controls, text="Center headings", variable=center_headings_var).grid(row=0, column=1, sticky="w", pady=3)
    ttk.Checkbutton(layout_controls, text="Hyphenation", variable=hyphenation_var).grid(row=1, column=0, sticky="w", pady=3)
    ttk.Checkbutton(layout_controls, text="Copy-friendly text (Bengali and complex scripts)", variable=copy_friendly_text_var).grid(row=4, column=0, sticky="w", pady=3)
    ttk.Label(layout_controls, text="Line height", style="Card.TLabel").grid(row=1, column=1, sticky="e", padx=(0, 6))
    ttk.Combobox(layout_controls, textvariable=line_height_var, values=["0.9", "1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.8", "2.0"], width=8).grid(row=1, column=2, sticky="w")
    ttk.Checkbutton(layout_controls, text="Indent first line", variable=indent_first_line_var).grid(row=2, column=0, sticky="w", pady=3)
    ttk.Entry(layout_controls, textvariable=indent_amount_var, width=10).grid(row=2, column=1, sticky="w")
    ttk.Label(layout_controls, text="Paragraph spacing", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=3)
    ttk.Combobox(layout_controls, textvariable=paragraph_spacing_var, values=["0pt", "3pt", "6pt", "9pt", "12pt", "Custom"], state="readonly", width=10).grid(row=3, column=1, sticky="w")
    ttk.Entry(layout_controls, textvariable=custom_paragraph_spacing_var, width=10).grid(row=3, column=2, sticky="w")

    options_frame = ttk.Frame(contents_tab)
    options_frame.pack(fill=tk.X)
    ttk.Checkbutton(options_frame, text="Include table of contents", variable=include_toc_var).grid(row=0, column=0, sticky="w", pady=3)
    ttk.Checkbutton(options_frame, text="Beautify contents", variable=beautify_toc_var).grid(row=0, column=1, sticky="w", pady=3)
    ttk.Label(options_frame, text="TOC language", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=3)
    ttk.Combobox(options_frame, textvariable=toc_language_var, values=["English", "Bangla"], state="readonly", width=13).grid(row=1, column=1, sticky="w")
    ttk.Label(options_frame, text="Title alignment", style="Card.TLabel").grid(row=1, column=2, sticky="w", pady=3)
    ttk.Combobox(options_frame, textvariable=toc_alignment_var, values=["Left", "Center", "Right"], state="readonly", width=13).grid(row=1, column=3, sticky="w")
    ttk.Label(options_frame, text="TOC design", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=3)
    ttk.Combobox(options_frame, textvariable=toc_design_var, values=["Classic", "Minimal", "Decorative"], state="readonly", width=13).grid(row=2, column=1, sticky="w")
    ttk.Checkbutton(options_frame, text="Decorative page border", variable=page_border_var).grid(row=2, column=2, columnspan=2, sticky="w", pady=3)
    ttk.Separator(options_frame).grid(row=3, column=0, columnspan=4, sticky="ew", pady=7)
    ttk.Checkbutton(options_frame, text="Show page numbers", variable=page_numbers_var).grid(row=4, column=0, sticky="w", pady=3)
    ttk.Label(options_frame, text="Language", style="Card.TLabel").grid(row=4, column=1, sticky="e", padx=(0, 6))
    ttk.Combobox(options_frame, textvariable=page_number_language_var, values=["English", "Bangla"], state="readonly", width=13).grid(row=4, column=2, sticky="w")
    ttk.Combobox(options_frame, textvariable=page_number_format_var, values=["Page 1 of 10", "1 / 10", "Page 1", "1"], state="readonly", width=18).grid(row=5, column=0, sticky="w")
    ttk.Combobox(options_frame, textvariable=page_number_style_var, values=["arabic", "roman", "Roman"], state="readonly", width=10).grid(row=5, column=1, sticky="w")
    ttk.Combobox(options_frame, textvariable=page_number_position_var, values=["Bottom left", "Middle", "Bottom right"], state="readonly", width=14).grid(row=5, column=2, sticky="w")
    ttk.Combobox(options_frame, textvariable=page_number_size_var, values=["8pt", "9pt", "10pt", "11pt", "12pt", "14pt"], state="readonly", width=7).grid(row=5, column=3, sticky="w")
    ttk.Separator(options_frame).grid(row=6, column=0, columnspan=4, sticky="ew", pady=7)
    ttk.Checkbutton(options_frame, text="Number TOC/front-matter pages", variable=front_page_numbers_var).grid(row=7, column=0, columnspan=2, sticky="w", pady=3)
    ttk.Label(options_frame, text="Front style", style="Card.TLabel").grid(row=8, column=0, sticky="w", pady=3)
    ttk.Combobox(options_frame, textvariable=front_page_number_style_var, values=["roman", "Roman", "arabic"], state="readonly", width=10).grid(row=8, column=1, sticky="w")
    ttk.Combobox(options_frame, textvariable=front_page_number_format_var, values=["Page 1 of 10", "1 / 10", "Page 1", "1"], state="readonly", width=18).grid(row=8, column=2, sticky="w")
    ttk.Label(options_frame, text="Language", style="Card.TLabel").grid(row=9, column=0, sticky="w", pady=3)
    ttk.Combobox(options_frame, textvariable=front_page_number_language_var, values=["English", "Bangla"], state="readonly", width=13).grid(row=9, column=1, sticky="w")
    ttk.Combobox(options_frame, textvariable=front_page_number_position_var, values=["Bottom left", "Middle", "Bottom right"], state="readonly", width=14).grid(row=9, column=2, sticky="w")
    ttk.Combobox(options_frame, textvariable=front_page_number_size_var, values=["8pt", "9pt", "10pt", "11pt", "12pt", "14pt"], state="readonly", width=7).grid(row=9, column=3, sticky="w")

    profile_row = ttk.Frame(profiles_tab)
    profile_row.pack(fill=tk.X, pady=(0, 8))
    profile_name_var = tk.StringVar()
    profile_choice_var = tk.StringVar()
    loaded_profile_name = [None]
    ttk.Label(profile_row, text="Profile", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 6))
    profile_picker = ttk.Combobox(profile_row, textvariable=profile_choice_var, values=[name for name in load_profiles() if name != LAST_USED_PROFILE], state="readonly", width=22)
    profile_picker.pack(side=tk.LEFT, padx=(0, 6))
    ttk.Entry(profile_row, textvariable=profile_name_var, width=18).pack(side=tk.LEFT, padx=(0, 6))

    profile_fields = {
        "page_size_choice": page_size_var, "orientation": orientation_var,
        "margin_choice": margin_var, "custom_margin": custom_margin_var,
        "font_size_choice": font_size_var, "custom_font_size": custom_font_size_var,
        "english_font": english_font_var, "heading_font": heading_font_var,
        "bengali_font": bengali_font_var, "arabic_font": arabic_font_var,
        "hyphenation": hyphenation_var, "line_height": line_height_var,
        "copy_friendly_text": copy_friendly_text_var,
        "page_numbers": page_numbers_var, "page_number_style": page_number_style_var,
        "page_number_format": page_number_format_var, "page_number_position": page_number_position_var,
        "front_page_numbers": front_page_numbers_var, "front_page_number_style": front_page_number_style_var,
        "front_page_number_format": front_page_number_format_var, "front_page_number_position": front_page_number_position_var,
        "front_page_number_size": front_page_number_size_var, "front_page_number_language": front_page_number_language_var,
        "page_number_size": page_number_size_var, "page_number_language": page_number_language_var,
        "indent_first_line": indent_first_line_var, "indent_amount": indent_amount_var,
        "paragraph_spacing": paragraph_spacing_var,
        "custom_paragraph_spacing": custom_paragraph_spacing_var,
        "center_headings": center_headings_var, "bold_headings": bold_headings_var,
        "include_toc": include_toc_var, "beautify_toc": beautify_toc_var,
        "toc_language": toc_language_var, "toc_alignment": toc_alignment_var,
        "toc_design": toc_design_var, "page_border": page_border_var,
        "output_name": output_name_var, "output_directory": output_directory_var,
    }

    def refresh_profiles():
        profile_picker.configure(values=[name for name in load_profiles() if name != LAST_USED_PROFILE])

    def current_settings():
        settings = {key: variable.get() for key, variable in profile_fields.items()}
        settings["paragraph_spacing"] = custom_paragraph_spacing_var.get() if paragraph_spacing_var.get() == "Custom" else paragraph_spacing_var.get()
        return settings

    def restore_last_session():
        last_settings = load_profiles().get(LAST_USED_PROFILE, {})
        for key, variable in profile_fields.items():
            if key in last_settings:
                variable.set(last_settings[key])
        if last_settings:
            profile_choice_var.set("Custom")

    restore_last_session()

    loading_profile = [False]

    def mark_profile_custom(*_args):
        if not loading_profile[0]:
            profile_choice_var.set("Custom")

    for variable in profile_fields.values():
        variable.trace_add("write", mark_profile_custom)

    def save_current_profile():
        name = profile_name_var.get().strip()
        if not name:
            messagebox.showerror("Profile", "Enter a new custom profile name. Built-in profiles are protected.")
            return
        try:
            save_profile(name, current_settings())
        except ValueError as error:
            messagebox.showerror("Profile", str(error))
            return
        profile_choice_var.set(name)
        loaded_profile_name[0] = name
        refresh_profiles()
        append_log(f"[PROFILE] Saved '{name}'.")

    def load_selected_profile():
        settings = load_profiles().get(profile_choice_var.get())
        if not settings:
            messagebox.showerror("Profile", "Select a saved profile first.")
            return
        loading_profile[0] = True
        for key, variable in profile_fields.items():
            if key in settings:
                if key == "paragraph_spacing" and settings[key] not in {"0pt", "3pt", "6pt", "9pt", "12pt"}:
                    paragraph_spacing_var.set("Custom")
                    custom_paragraph_spacing_var.set(settings[key])
                else:
                    variable.set(settings[key])
        loading_profile[0] = False
        selected_name = profile_choice_var.get()
        loaded_profile_name[0] = selected_name
        profile_name_var.set("" if selected_name in BUILT_IN_PROFILES else selected_name)
        append_log(f"[PROFILE] Loaded '{profile_choice_var.get()}'.")

    def delete_selected_profile():
        name = loaded_profile_name[0] or profile_choice_var.get()
        if name in BUILT_IN_PROFILES or name == LAST_USED_PROFILE:
            messagebox.showerror("Profile", "Built-in profiles cannot be deleted. Load it and save changes under a custom name.")
            return
        if not name or name == "Custom":
            messagebox.showerror("Profile", "Select a saved custom profile to delete.")
            return
        if not messagebox.askyesno("Delete profile", f"Delete the custom profile '{name}'?"):
            return
        if delete_profile(name):
            loaded_profile_name[0] = None
            profile_name_var.set("")
            profile_choice_var.set("Custom")
            refresh_profiles()
            append_log(f"[PROFILE] Deleted '{name}'.")

    profile_picker.bind("<<ComboboxSelected>>", lambda _event: load_selected_profile())

    ttk.Label(profile_row, text="Current profile", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(profile_row, text="Apply", command=load_selected_profile).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(profile_row, text="Save as / update", command=save_current_profile).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(profile_row, text="Delete custom", command=delete_selected_profile).pack(side=tk.LEFT)

    # --- Section 5: Mode ---
    mode_card = ttk.Frame(main_frame, style="Card.TFrame", padding=12)
    mode_card.pack(fill=tk.X, pady=(0, 15))
    ttk.Label(mode_card, text="5. Conversion Mode", style="Section.TLabel").pack(anchor="w", pady=(0, 6))

    mode_row = ttk.Frame(mode_card, style="Card.TFrame")
    mode_row.pack(fill=tk.X)
    ttk.Radiobutton(mode_row, text="⚡ Convert Once", variable=mode_var, value="once").pack(side=tk.LEFT, padx=(0, 20))
    ttk.Radiobutton(mode_row, text="🔄 Auto-Convert on File Save", variable=mode_var, value="auto").pack(side=tk.LEFT, padx=(0, 10))

    ttk.Label(mode_row, text="Check Interval (sec):", style="Card.TLabel").pack(side=tk.LEFT, padx=(10, 4))
    ttk.Spinbox(mode_row, from_=1, to=60, textvariable=interval_var, width=3).pack(side=tk.LEFT)

    # --- Log Output ---
    log_frame = ttk.Frame(main_frame)
    log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
    log_text = tk.Text(log_frame, height=5, font=("Consolas", 8), bg="#17212b", fg="#edf2f7", insertbackground="#edf2f7")
    log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=log_text.yview)
    log_text.configure(yscrollcommand=log_scroll.set)
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def append_log(msg):
        log_text.insert(tk.END, msg + "\n")
        log_text.see(tk.END)

    last_output_pdf = [None]

    # --- Actions Frame ---
    action_frame = ttk.Frame(main_frame)
    action_frame.pack(fill=tk.X)

    action_btn = ttk.Button(action_frame, text="🚀 Start PDF Conversion", style="Primary.TButton")
    action_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

    def open_pdf():
        if last_output_pdf[0] and Path(last_output_pdf[0]).exists():
            if sys.platform.startswith("win"):
                os.startfile(last_output_pdf[0])
            else:
                subprocess.Popen(["xdg-open", last_output_pdf[0]])
        elif OUTPUT_DIR.exists():
            if sys.platform.startswith("win"):
                os.startfile(str(OUTPUT_DIR))
            else:
                subprocess.Popen(["xdg-open", str(OUTPUT_DIR)])

    open_btn = ttk.Button(action_frame, text="📂 Open PDF", command=open_pdf)
    open_btn.pack(side=tk.RIGHT)

    def open_output_folder():
        folder = Path(last_output_pdf[0]).parent if last_output_pdf[0] else Path(output_directory_var.get() or OUTPUT_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(str(folder))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    ttk.Button(action_frame, text="Open output folder", command=open_output_folder).pack(side=tk.RIGHT, padx=(0, 8))

    status_lbl = ttk.Label(main_frame, textvariable=status_var, style="Status.TLabel")
    status_lbl.pack(anchor="w", pady=(6, 0))

    def run_conversion():
        infile = input_file_var.get().strip()
        files = list(selected_files) or ([infile] if infile and Path(infile).exists() else [])
        if not files or any(not Path(path).exists() for path in files):
            messagebox.showerror("Error", "Please select one or more supported input documents.")
            return

        psize = page_size_var.get()
        fsize = font_size_var.get()
        custom_pt = custom_font_size_var.get() if fsize == "Custom" else None
        paragraph_spacing = custom_paragraph_spacing_var.get().strip() if paragraph_spacing_var.get() == "Custom" else paragraph_spacing_var.get()
        options = dict(english_font=english_font_var.get().strip() or "DejaVu Sans", heading_font=heading_font_var.get().strip() or english_font_var.get().strip() or "DejaVu Sans", bengali_font=bengali_font_var.get().strip() or "SolaimanLipi", arabic_font=arabic_font_var.get().strip() or "Amiri", margin_choice=margin_var.get(), custom_margin=custom_margin_var.get().strip() or "1in", orientation=orientation_var.get(), page_numbers=page_numbers_var.get(), page_number_style=page_number_style_var.get(), page_number_format=page_number_format_var.get(), page_number_position=page_number_position_var.get(), page_number_size=page_number_size_var.get(), page_number_language=page_number_language_var.get(), front_page_numbers=front_page_numbers_var.get(), front_page_number_style=front_page_number_style_var.get(), front_page_number_format=front_page_number_format_var.get(), front_page_number_position=front_page_number_position_var.get(), front_page_number_size=front_page_number_size_var.get(), front_page_number_language=front_page_number_language_var.get(), indent_first_line=indent_first_line_var.get(), indent_amount=indent_amount_var.get().strip() or "0.25in", paragraph_spacing=paragraph_spacing, center_headings=center_headings_var.get(), bold_headings=bold_headings_var.get(), include_toc=include_toc_var.get(), beautify_toc=beautify_toc_var.get(), toc_language=toc_language_var.get(), page_border=page_border_var.get(), toc_alignment=toc_alignment_var.get(), toc_design=toc_design_var.get(), hyphenation=hyphenation_var.get(), line_height=line_height_var.get(), copy_friendly_text=copy_friendly_text_var.get(), output_directory=output_directory_var.get().strip() or str(OUTPUT_DIR))
        output_name = output_name_var.get().strip() or None
        save_last_used_settings(current_settings())

        action_btn.config(state="disabled")
        status_var.set("Converting... please wait.")
        append_log(f"[{time.strftime('%H:%M:%S')}] Starting conversion...")

        def worker():
            batch_results = convert_many_to_pdf(files, log_func=append_log, output_name=output_name, page_size_choice=psize, font_size_choice=fsize, custom_font_size=custom_pt, **options)
            failures = [(source, result) for source, success, result in batch_results if not success]
            last_success = next(((success, result) for _source, success, result in reversed(batch_results) if success), (False, "No PDF was created."))
            summary = f"{len(batch_results) - len(failures)} of {len(batch_results)} files converted."
            if failures:
                summary += " Failed: " + ", ".join(Path(source).name for source, _result in failures)
            root.after(0, lambda: on_finish(*last_success, summary=summary))

        def on_finish(success, res, summary=""):
            action_btn.config(state="normal")
            if success:
                last_output_pdf[0] = res
                status_var.set(summary or f"Completed: {Path(res).name}")
            else:
                status_var.set("Conversion failed. Check log above.")

        threading.Thread(target=worker, daemon=True).start()

    def toggle_watch():
        if is_watching[0]:
            # Stop watching
            is_watching[0] = False
            action_btn.config(text="🚀 Start PDF Conversion")
            status_var.set("Watching stopped.")
            append_log(f"[{time.strftime('%H:%M:%S')}] Stopped file watching.")
            return

        infile = input_file_var.get().strip()
        watch_files = list(selected_files) or ([infile] if infile and Path(infile).exists() else [])
        if len(watch_files) != 1 or not Path(watch_files[0]).exists():
            messagebox.showerror("Error", "Auto-convert requires exactly one supported input document.")
            return
        infile = watch_files[0]
        save_last_used_settings(current_settings())

        is_watching[0] = True
        action_btn.config(text="⏹ Stop Auto-Convert")
        status_var.set("Auto-convert active. Watching for changes...")
        append_log(f"[{time.strftime('%H:%M:%S')}] Auto-convert started on: {Path(infile).name}")

        def watch_loop():
            psize = page_size_var.get()
            fsize = font_size_var.get()
            custom_pt = custom_font_size_var.get() if fsize == "Custom" else None
            paragraph_spacing = custom_paragraph_spacing_var.get().strip() if paragraph_spacing_var.get() == "Custom" else paragraph_spacing_var.get()
            options = dict(english_font=english_font_var.get().strip() or "DejaVu Sans", heading_font=heading_font_var.get().strip() or english_font_var.get().strip() or "DejaVu Sans", bengali_font=bengali_font_var.get().strip() or "SolaimanLipi", arabic_font=arabic_font_var.get().strip() or "Amiri", margin_choice=margin_var.get(), custom_margin=custom_margin_var.get().strip() or "1in", orientation=orientation_var.get(), page_numbers=page_numbers_var.get(), page_number_style=page_number_style_var.get(), page_number_format=page_number_format_var.get(), page_number_position=page_number_position_var.get(), page_number_size=page_number_size_var.get(), page_number_language=page_number_language_var.get(), indent_first_line=indent_first_line_var.get(), indent_amount=indent_amount_var.get().strip() or "0.25in", paragraph_spacing=paragraph_spacing, center_headings=center_headings_var.get(), bold_headings=bold_headings_var.get(), include_toc=include_toc_var.get(), beautify_toc=beautify_toc_var.get(), toc_language=toc_language_var.get(), page_border=page_border_var.get(), toc_alignment=toc_alignment_var.get(), toc_design=toc_design_var.get(), hyphenation=hyphenation_var.get(), line_height=line_height_var.get(), output_directory=output_directory_var.get().strip() or str(OUTPUT_DIR), output_name=output_name_var.get().strip() or None)
            interval = max(1, interval_var.get())

            # Initial compile
            success, res = convert_md_to_pdf(infile, psize, fsize, custom_pt, log_func=append_log, **options)
            if success:
                last_output_pdf[0] = res

            last_mtime = Path(infile).stat().st_mtime
            while is_watching[0]:
                time.sleep(interval)
                if not Path(infile).exists():
                    continue
                curr_mtime = Path(infile).stat().st_mtime
                if curr_mtime != last_mtime:
                    last_mtime = curr_mtime
                    append_log(f"\n[{time.strftime('%H:%M:%S')}] File modified! Re-compiling...")
                    success, res = convert_md_to_pdf(infile, psize, fsize, custom_pt, log_func=append_log, **options)
                    if success:
                        last_output_pdf[0] = res
                        root.after(0, lambda: status_var.set(f"Updated: {time.strftime('%H:%M:%S')}"))

        watch_thread[0] = threading.Thread(target=watch_loop, daemon=True)
        watch_thread[0].start()

    def handle_action():
        if mode_var.get() == "auto":
            toggle_watch()
        else:
            run_conversion()

    action_btn.config(command=handle_action)

    def close_app():
        save_last_used_settings(current_settings())
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_app)

    # If launched in auto mode, start watch automatically
    if auto_mode_init:
        root.after(500, toggle_watch)

    apply_theme()
    root.mainloop()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        cli_interactive_flow(auto_mode="--auto" in sys.argv)
    elif "--auto" in sys.argv:
        launch_gui(auto_mode_init=True)
    else:
        launch_gui(auto_mode_init=False)
