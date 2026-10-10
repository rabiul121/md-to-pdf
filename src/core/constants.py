"""
Shared constants, paths, and default configurations for md-to-pdf.
"""

import os
import sys
from pathlib import Path

# Base directories - resolves project root correctly
_here = Path(__file__).resolve().parent  # src/core
_src_dir = _here.parent                  # src
_root_dir = _src_dir.parent              # project root

BASE_DIR = _root_dir if (_root_dir / "assets" / "fonts").exists() else _src_dir
APP_DIR = _src_dir
INPUT_DIR = BASE_DIR / "input"
TEMPLATE_PATH = APP_DIR / "template.tex"
LUA_FILTER_PATH = APP_DIR / "font_filter.lua"
if getattr(sys, "frozen", False):
    _local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    APP_DATA_DIR = _local_app_data / "PDF Creator Studio"
    _legacy_app_data_dir = _local_app_data / "Markdown to PDF Studio"
    if not APP_DATA_DIR.exists() and _legacy_app_data_dir.exists():
        # Carry profiles over from the pre-rename application folder.
        try:
            _legacy_app_data_dir.rename(APP_DATA_DIR)
        except OSError:
            APP_DATA_DIR = _legacy_app_data_dir
    OUTPUT_DIR = Path.home() / "Documents" / "Markdown to PDF"
    PROFILE_PATH = APP_DATA_DIR / "profiles.json"
else:
    APP_DATA_DIR = BASE_DIR
    OUTPUT_DIR = BASE_DIR / "output"
    PROFILE_PATH = BASE_DIR / "profiles.json"
LAST_USED_PROFILE = "_last_used"
SUPPORTED_INPUT_EXTENSIONS = {".md", ".markdown", ".txt", ".doc", ".docx", ".epub", ".mobi"}

# Page sizes and margin presets
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

PAGE_DEFAULT_MARGINS = {
    "For Mobile": "7mm",
    "For PC": "1.2in",
}

FONT_SIZES = {
    "Standard": "11pt",
    "Medium": "14pt",
    "Large": "17pt",
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
