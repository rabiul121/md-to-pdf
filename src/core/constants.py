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
CODING_FONT_CHOICES = [
    "JetBrains Mono", "MonoLisa", "Operator Mono", "DejaVu Sans",
]

PROFILE_BASE_SETTINGS = {
    "page_size_choice": "A4", "orientation": "Portrait", "margin_choice": "Page default",
    "custom_margin": "25mm", "font_size_choice": "Medium", "custom_font_size": 14,
    "english_font": "DejaVu Sans", "heading_font": "DejaVu Sans",
    "bengali_font": "SolaimanLipi", "arabic_font": "Amiri",
    "code_font": "JetBrains Mono",
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
    "English": {"toc_language": "English", "page_number_language": "English", "english_font": "DejaVu Sans", "code_font": "JetBrains Mono"},
    "Bangla": {"toc_language": "Bangla", "page_number_language": "Bangla", "bengali_font": "SolaimanLipi", "code_font": "JetBrains Mono"},
}

# Names of built-in profiles that were removed during the UI redesign. Saved
# overrides for these names are legacy data and are ignored by the loader so
# they no longer appear next to the four supported built-in presets. Profiles
# saved under any other custom name remain untouched.
REMOVED_BUILT_IN_PROFILES = {
    "Book Print - EB Garamond",
    "Book Print - Alegreya",
    "Book Print - Crimson Text",
    "Book Print - Georgia",
    "Minimal",
    "Decorative",
    "Profile_1",
    "Custome_1",
    "Novel Preset",
    "Georgia-Arial",
    "Bangla_Update",
    "Storybook Preset",
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
    "coading": {
        "JetBrains Mono": "JetBrainsMono-VariableFont_wght.ttf",
        "MonoLisa": "MonoLisa-Regular.ttf",
        "Operator Mono": "OperatorMono-Book.ttf",
    },
    "coding": {
        "JetBrains Mono": "JetBrainsMono-VariableFont_wght.ttf",
        "MonoLisa": "MonoLisa-Regular.ttf",
        "Operator Mono": "OperatorMono-Book.ttf",
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
