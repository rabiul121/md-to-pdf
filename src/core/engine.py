"""
Core conversion engine: Pandoc + XeLaTeX compilation, font resolution, and batch processing.
"""

import os
import sys
import shutil
import subprocess
import tempfile
import re
from pathlib import Path

from src.core.images import prepare_remote_images
from src.core.editor import escape_plain_text

from src.core.constants import (
    BASE_DIR,
    OUTPUT_DIR,
    TEMPLATE_PATH,
    LUA_FILTER_PATH,
    SUPPORTED_INPUT_EXTENSIONS,
    PAGE_SIZES,
    PAGE_DEFAULT_MARGINS,
    MARGIN_PRESETS,
    FONT_SIZES,
    BUNDLED_FONT_FILES,
)


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


def font_style_features(font_selection):
    """Map file-based fonts to sibling styles, synthesizing missing faces.

    XeLaTeX cannot discover a font family when fontspec loads a filename.
    Variable fonts also need a synthetic fallback with the XeTeX renderer.
    """
    filename, directory = font_selection
    regular = Path(filename)
    stem = regular.stem
    base = re.sub(r"-(?:Regular|Book)$", "", stem)

    def sibling(*styles):
        for style in styles:
            candidate = f"{base}-{style}{regular.suffix}"
            if (Path(directory) / candidate).is_file():
                return candidate
        return None

    bold = sibling("Bold")
    italic = sibling("Italic", "It", "Oblique")
    bold_italic = sibling("BoldItalic", "BoldIt", "BoldOblique")
    options = [f"BoldFont={{{bold or filename}}}"]
    if not bold:
        options.append("BoldFeatures={FakeBold=2}")
    options.append(f"ItalicFont={{{italic or filename}}}")
    if not italic:
        options.append("ItalicFeatures={FakeSlant=0.2}")
    options.append(f"BoldItalicFont={{{bold_italic or italic or bold or filename}}}")
    if not bold_italic:
        features = []
        if italic or not bold:
            features.append("FakeBold=2")
        if not italic:
            features.append("FakeSlant=0.2")
        options.append("BoldItalicFeatures={" + ",".join(features) + "}")
    return ",".join(options)


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


def get_font_families(root=None, project_fonts=None):
    """Return project font options first, followed by installed system fonts A-Z."""
    if project_fonts is None:
        project_fonts = []
    temporary_root = None
    try:
        if root is None:
            import tkinter as tk

            temporary_root = tk.Tk()
            temporary_root.withdraw()
            root = temporary_root
        from tkinter import font as tkinter_font
        installed_fonts = tkinter_font.families(root)
    except Exception:
        installed_fonts = []
    finally:
        if temporary_root is not None:
            temporary_root.destroy()

    project_fonts = list(dict.fromkeys(project_fonts))
    project_names = {name.casefold() for name in project_fonts}
    system_fonts = sorted(
        {name for name in installed_fonts if name.casefold() not in project_names},
        key=str.casefold,
    )
    return project_fonts + system_fonts


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


def convert_md_to_pdf(
    input_file,
    page_size_choice="A4",
    font_size_choice="Medium",
    custom_font_size=None,
    output_file=None,
    log_func=print,
    english_font="DejaVu Sans",
    bengali_font="SolaimanLipi",
    arabic_font="Amiri",
    margin_choice="Page default",
    custom_margin=None,
    orientation="Portrait",
    page_numbers=False,
    page_number_style="arabic",
    page_number_format="Page 1 of 10",
    page_number_position="Middle",
    page_number_size="9pt",
    front_page_numbers=False,
    front_page_number_style="roman",
    front_page_number_format="1",
    front_page_number_position="Middle",
    front_page_number_size="9pt",
    front_page_number_language="English",
    indent_first_line=False,
    indent_amount="0.25in",
    center_headings=True,
    bold_headings=True,
    include_toc=True,
    beautify_toc=True,
    output_name=None,
    output_directory=None,
    toc_language="English",
    page_number_language="English",
    page_border=False,
    toc_alignment="Center",
    toc_design="Classic",
    heading_font="DejaVu Sans",
    hyphenation=True,
    line_height="1.1",
    paragraph_spacing="6pt",
    copy_friendly_text=False,
    input_format=None,
    highlight_style="tango",
):
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
    if highlight_style:
        cmd.append(f"--highlight-style={highlight_style}")

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
