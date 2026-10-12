"""
Modern Material Design 3 interface for md-to-pdf powered by Flet (Flutter for Python).
"""

import asyncio
import time
import threading
import tempfile
from pathlib import Path

import flet as ft

from src.core.constants import (
    BASE_DIR,
    INPUT_DIR,
    OUTPUT_DIR,
    SUPPORTED_INPUT_EXTENSIONS,
    PAGE_SIZES,
    PAGE_DEFAULT_MARGINS,
    MARGIN_PRESETS,
    FONT_SIZES,
    PROJECT_FONT_CHOICES,
    HEADING_FONT_CHOICES,
    PROFILE_BASE_SETTINGS,
    BUILT_IN_PROFILES,
    LAST_USED_PROFILE,
)
from src.core.profiles import (
    load_profiles,
    load_last_used_settings,
    save_profile,
    update_profile,
    save_last_used_settings,
    delete_profile,
)
from src.core.engine import (
    convert_md_to_pdf,
    convert_many_to_pdf,
    get_font_families,
    open_in_system,
)
from src.core.editor import (
    bold_producer,
    bullet_producer,
    code_block_producer,
    heading_producer,
    horizontal_rule_producer,
    inline_code_producer,
    italic_producer,
    link_producer,
    ordered_list_producer,
    quote_producer,
    strikethrough_producer,
)
from src.core.markdown_preview import markdown_to_controls
from src.core.help_topics import HELP_TOPICS, search_help_topics


async def main(page: ft.Page):
    last_used_settings = load_last_used_settings()
    try:
        initial_theme_mode = ft.ThemeMode(last_used_settings.get("theme_mode", ft.ThemeMode.SYSTEM.value))
    except ValueError:
        initial_theme_mode = ft.ThemeMode.SYSTEM

    page.title = "PDF Creator Studio"
    page.window.width = 1180
    page.window.height = 860
    page.window.min_width = 800
    page.window.min_height = 680
    page.theme_mode = initial_theme_mode
    page.padding = 16

    def is_light_theme():
        """Resolve System mode against the OS brightness for code palettes."""
        if page.theme_mode == ft.ThemeMode.LIGHT:
            return True
        if page.theme_mode == ft.ThemeMode.DARK:
            return False
        return page.platform_brightness == ft.Brightness.LIGHT

    # State tracking
    selected_files = []
    is_watching = [False]
    watch_task = [None]
    last_converted_pdf = [None]

    # Pre-populate detected input files
    initial_files = (
        sorted(
            path
            for path in INPUT_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS
        )
        if INPUT_DIR.exists()
        else []
    )
    if initial_files:
        selected_files.append(str(initial_files[0]))

    # File picker control - registered as a service so pick/save dialogs
    # open asynchronously when the UI buttons are clicked.
    file_picker = ft.FilePicker()
    page.services.append(file_picker)
    clipboard = ft.Clipboard()
    page.services.append(clipboard)

    # Output directory and custom filename
    output_dir_val = [str(OUTPUT_DIR)]

    # ---------------- UI Controls ----------------
    # Header / AppBar
    def update_theme_button():
        if page.theme_mode == ft.ThemeMode.SYSTEM:
            theme_btn.icon = ft.Icons.BRIGHTNESS_AUTO
            theme_btn.tooltip = "Theme: System (click for Light)"
        elif page.theme_mode == ft.ThemeMode.LIGHT:
            theme_btn.icon = ft.Icons.LIGHT_MODE_OUTLINED
            theme_btn.tooltip = "Theme: Light (click for Dark)"
        else:
            theme_btn.icon = ft.Icons.DARK_MODE_OUTLINED
            theme_btn.tooltip = "Theme: Dark (click for System)"

    def toggle_theme(e):
        theme_cycle = (ft.ThemeMode.SYSTEM, ft.ThemeMode.LIGHT, ft.ThemeMode.DARK)
        current_index = theme_cycle.index(page.theme_mode)
        page.theme_mode = theme_cycle[(current_index + 1) % len(theme_cycle)]
        update_theme_button()
        apply_log_theme()
        refresh_preview()
        save_last_used_settings(
            collect_current_settings(),
            selected_profile=profile_dropdown.value,
        )
        page.update()

    def handle_platform_brightness_change(_e):
        if page.theme_mode == ft.ThemeMode.SYSTEM:
            apply_log_theme()
            refresh_preview()
            page.update()

    theme_btn = ft.IconButton(
        icon=ft.Icons.LIGHT_MODE_OUTLINED,
        tooltip="Switch to Light Mode",
        on_click=toggle_theme,
    )
    update_theme_button()

    open_output_btn = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN_OUTLINED,
        tooltip="Open Output Folder",
        on_click=lambda e: open_in_system(output_dir_val[0]),
    )

    def open_help_tab(_e=None):
        """Jump to the built-in Help tab (falls back to the user guide file)."""
        try:
            tabs.selected_index = 6
            page.update()
        except NameError:
            open_in_system(BASE_DIR / "docs" / "USER_GUIDE.md")

    help_btn = ft.IconButton(
        icon=ft.Icons.HELP_OUTLINE,
        tooltip="Open the in-app Help tab",
        on_click=open_help_tab,
    )

    app_bar = ft.AppBar(
        leading=ft.Icon(ft.Icons.PICTURE_AS_PDF_ROUNDED, color=ft.Colors.AMBER_400),
        title=ft.Text("PDF Creator Studio", weight=ft.FontWeight.BOLD),
        center_title=False,
        actions=[open_output_btn, theme_btn, help_btn, ft.Container(width=8)],
    )
    page.appbar = app_bar

    # Files tab controls
    selected_files_text = ft.Text(
        value=Path(selected_files[0]).name if selected_files else "No document selected",
        weight=ft.FontWeight.W_500,
        expand=True,
    )
    output_name_field = ft.TextField(
        label="Custom Output Name",
        hint_text="Leave blank to use source filename",
        dense=True,
        expand=True,
    )
    output_dir_field = ft.TextField(
        label="Output Folder",
        value=str(OUTPUT_DIR),
        dense=True,
        expand=True,
        read_only=True,
    )

    async def pick_single_file(e):
        picked = await file_picker.pick_files(
            dialog_title="Select a Markdown or Document File",
            allowed_extensions=["md", "markdown", "txt", "docx", "doc", "epub", "mobi"],
        )
        if picked:
            selected_files.clear()
            selected_files.append(picked[0].path)
            selected_files_text.value = Path(picked[0].path).name
            page.update()

    async def pick_batch_files(e):
        picked = await file_picker.pick_files(
            dialog_title="Select Files for Batch Conversion",
            allow_multiple=True,
            allowed_extensions=["md", "markdown", "txt", "docx", "doc", "epub", "mobi"],
        )
        if picked:
            selected_files.clear()
            selected_files.extend(f.path for f in picked)
            selected_files_text.value = f"{len(picked)} files selected: {', '.join(Path(f.path).name for f in picked[:3])}{'...' if len(picked) > 3 else ''}"
            page.update()

    async def pick_output_dir(e):
        chosen = await file_picker.get_directory_path(dialog_title="Select Output Directory")
        if chosen:
            output_dir_val[0] = chosen
            output_dir_field.value = chosen
            page.update()

    async def handle_file_picker_result(e):
        """Handle FilePicker result events (fires when async pick/save dialog closes)."""
        files = e.files
        if not files or len(files) == 0:
            return

        # The result is a list of FilePickerFile objects.
        for _file in files:
            if _file.path:
                # When the caller has already consumed the async result (e.g.
                # pick_files / get_directory_path returned the path), avoid
                # processing it again here - the async path is authoritative.
                if getattr(handle_file_picker_result, "_async_done", False):
                    handle_file_picker_result._async_done = False
                    return

    # Quick selector chips
    def select_quick_doc(path_str):
        selected_files.clear()
        selected_files.append(path_str)
        selected_files_text.value = Path(path_str).name
        page.update()

    quick_chips = [
        ft.Chip(
            label=ft.Text(f.name),
            on_click=lambda e, p=str(f): select_quick_doc(p),
        )
        for f in initial_files[:6]
    ]

    files_tab = ft.Container(
        content=ft.Column(
            [
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Source Documents", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED),
                                        selected_files_text,
                                        ft.FilledTonalButton("Choose File", icon=ft.Icons.FILE_OPEN, on_click=pick_single_file),
                                        ft.OutlinedButton("Batch Select", icon=ft.Icons.FILE_COPY_OUTLINED, on_click=pick_batch_files),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Divider(),
                                ft.Text("Discovered in Project Input Folder:", size=12, color=ft.Colors.GREY_400),
                                ft.Row(quick_chips, wrap=True) if quick_chips else ft.Text("No sample files found in input/", italic=True),
                            ],
                            spacing=12,
                        ),
                        padding=16,
                    )
                ),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Destination Settings", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row([output_name_field]),
                                ft.Row(
                                    [
                                        output_dir_field,
                                        ft.FilledTonalButton("Choose Folder", icon=ft.Icons.FOLDER, on_click=pick_output_dir),
                                    ]
                                ),
                            ],
                            spacing=12,
                        ),
                        padding=16,
                    )
                ),
            ],
            spacing=12,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=10,
    )

    # ---------------- Page & Geometry Tab ----------------
    page_size_dropdown = ft.Dropdown(
        label="Paper Size",
        value="A4",
        options=[ft.dropdown.Option(k) for k in PAGE_SIZES.keys()],
        expand=True,
    )
    orientation_dropdown = ft.Dropdown(
        label="Orientation",
        value="Portrait",
        options=[ft.dropdown.Option("Portrait"), ft.dropdown.Option("Landscape")],
        expand=True,
    )
    margin_dropdown = ft.Dropdown(
        label="Margin Preset",
        value="Page default",
        options=[ft.dropdown.Option("Page default"), *[ft.dropdown.Option(m) for m in MARGIN_PRESETS.keys()], ft.dropdown.Option("Custom")],
        expand=True,
    )
    custom_margin_field = ft.TextField(
        label="Custom Margin",
        value="25mm",
        hint_text="e.g. 1in, 20mm, 0.75in",
        dense=True,
        expand=True,
    )
    page_border_switch = ft.Switch(label="Decorative Page Border", value=False)

    geometry_tab = ft.Container(
        content=ft.Column(
            [
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Page Dimensions & Layout", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row([page_size_dropdown, orientation_dropdown], spacing=16),
                                ft.Row([margin_dropdown, custom_margin_field], spacing=16),
                                ft.Row([page_border_switch]),
                            ],
                            spacing=14,
                        ),
                        padding=16,
                    )
                )
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=10,
    )

    # ---------------- Typography Tab ----------------
    font_families = {
        "Bengali": get_font_families(project_fonts=PROJECT_FONT_CHOICES["Bengali"]),
        "Arabic": get_font_families(project_fonts=PROJECT_FONT_CHOICES["Arabic"]),
        "English": get_font_families(project_fonts=PROJECT_FONT_CHOICES["English"]),
        "Headings": get_font_families(project_fonts=HEADING_FONT_CHOICES),
    }
    bengali_font_dd = ft.Dropdown(
        label="Bengali Font (বাংলা)",
        value="SolaimanLipi",
        options=[ft.dropdown.Option(f) for f in font_families["Bengali"]],
        expand=True,
    )
    arabic_font_dd = ft.Dropdown(
        label="Arabic Font (العربية)",
        value="Amiri",
        options=[ft.dropdown.Option(f) for f in font_families["Arabic"]],
        expand=True,
    )
    english_font_dd = ft.Dropdown(
        label="English Font",
        value="DejaVu Sans",
        options=[ft.dropdown.Option(f) for f in font_families["English"]],
        expand=True,
    )
    heading_font_dd = ft.Dropdown(
        label="Heading Font",
        value="DejaVu Sans",
        options=[ft.dropdown.Option(f) for f in font_families["Headings"]],
        expand=True,
    )

    font_dropdowns = {
        "Bengali": bengali_font_dd,
        "Arabic": arabic_font_dd,
        "English": english_font_dd,
        "Headings": heading_font_dd,
    }

    font_dropdown_roles = {id(dropdown): role for role, dropdown in font_dropdowns.items()}
    selected_font_values = {}
    font_search_queries = {}

    def handle_font_focus(e):
        dropdown = e.control
        if dropdown.value is not None:
            selected_font_values[id(dropdown)] = dropdown.value
        font_search_queries[id(dropdown)] = ""
        # Clear the selected label so the first keystroke starts a fresh query
        # (Flet's editable dropdown otherwise appends to the current value).
        dropdown.value = None
        page.update()

    def handle_font_text_change(e):
        dropdown = e.control
        query = (e.data if e.data is not None else dropdown.text or "").strip()
        font_search_queries[id(dropdown)] = query
        role = font_dropdown_roles.get(id(dropdown))
        if not role or not query:
            return
        folded = query.casefold()
        exact = next(
            (family for family in font_families[role] if family.casefold() == folded),
            None,
        )
        if exact and dropdown.value != exact:
            dropdown.value = exact
            selected_font_values[id(dropdown)] = exact
            page.update()

    def handle_font_blur(e):
        dropdown = e.control
        if dropdown.value is not None:
            return
        query = font_search_queries.get(id(dropdown), "").strip().casefold()
        role = font_dropdown_roles.get(id(dropdown))
        exact = (
            next(
                (family for family in font_families[role] if family.casefold() == query),
                None,
            )
            if role and query
            else None
        )
        dropdown.value = exact or selected_font_values.get(id(dropdown))
        font_search_queries[id(dropdown)] = ""
        page.update()

    def handle_font_select(e):
        dropdown = e.control
        value = e.data if e.data is not None else dropdown.value
        dropdown.value = value
        selected_font_values[id(dropdown)] = value
        font_search_queries[id(dropdown)] = ""

    for font_dropdown in font_dropdowns.values():
        font_dropdown.editable = True
        font_dropdown.enable_filter = True
        font_dropdown.enable_search = True
        font_dropdown.leading_icon = ft.Icons.SEARCH
        font_dropdown.hint_text = "Type to search fonts"
        font_dropdown.dense = True
        font_dropdown.menu_height = 280
        font_dropdown.on_focus = handle_font_focus
        font_dropdown.on_blur = handle_font_blur
        font_dropdown.on_text_change = handle_font_text_change
        font_dropdown.on_select = handle_font_select

    font_size_dd = ft.Dropdown(
        label="Font Size Preset",
        value="Medium",
        options=[ft.dropdown.Option("Standard"), ft.dropdown.Option("Medium"), ft.dropdown.Option("Large"), ft.dropdown.Option("Custom")],
        expand=True,
    )
    custom_font_size_field = ft.TextField(
        label="Custom Font Size (pt)",
        value="14",
        dense=True,
        expand=True,
    )
    line_height_dd = ft.Dropdown(
        label="Line Spacing Multiplier",
        value="1.1",
        options=[ft.dropdown.Option("1.0"), ft.dropdown.Option("1.1"), ft.dropdown.Option("1.15"), ft.dropdown.Option("1.2"), ft.dropdown.Option("1.25"), ft.dropdown.Option("1.5")],
        expand=True,
    )
    paragraph_spacing_dd = ft.Dropdown(
        label="Paragraph Spacing",
        value="6pt",
        options=[ft.dropdown.Option("0pt"), ft.dropdown.Option("3pt"), ft.dropdown.Option("6pt"), ft.dropdown.Option("9pt"), ft.dropdown.Option("12pt")],
        expand=True,
    )

    bold_headings_switch = ft.Switch(label="Bold Headings", value=True)
    center_headings_switch = ft.Switch(label="Center Headings", value=True)
    hyphenation_switch = ft.Switch(label="Hyphenation", value=True)
    indent_switch = ft.Switch(label="First Line Indent", value=False)
    indent_amount_field = ft.TextField(label="Indent Amount", value="0.25in", dense=True, width=120)

    typography_tab = ft.Container(
        content=ft.Column(
            [
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Multilingual Fonts", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row([bengali_font_dd, arabic_font_dd], spacing=16),
                                ft.Row([english_font_dd, heading_font_dd], spacing=16),
                            ],
                            spacing=14,
                        ),
                        padding=16,
                    )
                ),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Sizes & Paragraph Formatting", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row([font_size_dd, custom_font_size_field], spacing=16),
                                ft.Row([line_height_dd, paragraph_spacing_dd], spacing=16),
                                ft.Row([bold_headings_switch, center_headings_switch, hyphenation_switch], wrap=True),
                                ft.Row([indent_switch, indent_amount_field]),
                            ],
                            spacing=14,
                        ),
                        padding=16,
                    )
                ),
            ],
            spacing=12,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=10,
    )

    # ---------------- Contents & TOC Tab ----------------
    include_toc_switch = ft.Switch(label="Include Table of Contents", value=True)
    beautify_toc_switch = ft.Switch(label="Beautify TOC", value=True)
    toc_language_dd = ft.Dropdown(
        label="TOC Language",
        value="English",
        options=[ft.dropdown.Option("English"), ft.dropdown.Option("Bangla")],
        expand=True,
    )
    toc_alignment_dd = ft.Dropdown(
        label="TOC Title Alignment",
        value="Center",
        options=[ft.dropdown.Option("Left"), ft.dropdown.Option("Center"), ft.dropdown.Option("Right")],
        expand=True,
    )
    toc_design_dd = ft.Dropdown(
        label="TOC Design",
        value="Classic",
        options=[ft.dropdown.Option("Classic"), ft.dropdown.Option("Minimal"), ft.dropdown.Option("Decorative")],
        expand=True,
    )

    page_numbers_switch = ft.Switch(label="Page Numbers", value=False)
    page_number_position_dd = ft.Dropdown(
        label="Position",
        value="Middle",
        options=[ft.dropdown.Option("Bottom left"), ft.dropdown.Option("Middle"), ft.dropdown.Option("Bottom right")],
        expand=True,
    )
    page_number_format_dd = ft.Dropdown(
        label="Format",
        value="Page 1 of 10",
        options=[ft.dropdown.Option("Page 1 of 10"), ft.dropdown.Option("1 / 10"), ft.dropdown.Option("Page 1"), ft.dropdown.Option("1")],
        expand=True,
    )
    page_number_language_dd = ft.Dropdown(
        label="Numeral Language",
        value="English",
        options=[ft.dropdown.Option("English"), ft.dropdown.Option("Bangla")],
        expand=True,
    )

    toc_tab = ft.Container(
        content=ft.Column(
            [
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Table of Contents (TOC)", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row([include_toc_switch, beautify_toc_switch]),
                                ft.Row([toc_language_dd, toc_alignment_dd, toc_design_dd], spacing=16),
                            ],
                            spacing=14,
                        ),
                        padding=16,
                    )
                ),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Page Numbering", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row([page_numbers_switch]),
                                ft.Row([page_number_position_dd, page_number_format_dd, page_number_language_dd], spacing=16),
                            ],
                            spacing=14,
                        ),
                        padding=16,
                    )
                ),
            ],
            spacing=12,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=10,
    )

    # ---------------- Profiles Tab ----------------
    profiles_dict = load_profiles()
    profile_names = [name for name in profiles_dict if name != LAST_USED_PROFILE]
    saved_profile_name = last_used_settings.get("selected_profile")
    selected_profile_name = saved_profile_name if saved_profile_name in profile_names else (profile_names[0] if profile_names else None)

    def is_profile_selected(name):
        return bool(name) and name != LAST_USED_PROFILE

    profile_dropdown = ft.Dropdown(
        label="Choose Profile Preset",
        value=selected_profile_name,
        options=[ft.dropdown.Option(name) for name in profile_names],
        expand=True,
    )
    save_profile_field = ft.TextField(label="New Profile Name", hint_text="e.g. My Novel Preset", dense=True, expand=True)

    def collect_current_settings():
        custom_pt = None
        if font_size_dd.value == "Custom":
            try:
                custom_pt = int(custom_font_size_field.value.strip())
            except ValueError:
                custom_pt = 14

        return {
            "theme_mode": page.theme_mode.value,
            "page_size_choice": page_size_dropdown.value,
            "orientation": orientation_dropdown.value,
            "margin_choice": margin_dropdown.value,
            "custom_margin": custom_margin_field.value.strip() or "25mm",
            "font_size_choice": font_size_dd.value,
            "custom_font_size": custom_pt or 14,
            "english_font": english_font_dd.value,
            "heading_font": heading_font_dd.value,
            "bengali_font": bengali_font_dd.value,
            "arabic_font": arabic_font_dd.value,
            "page_numbers": page_numbers_switch.value,
            "page_number_style": "arabic",
            "page_number_format": page_number_format_dd.value,
            "page_number_position": page_number_position_dd.value,
            "page_number_size": "9pt",
            "page_number_language": page_number_language_dd.value,
            "indent_first_line": indent_switch.value,
            "indent_amount": indent_amount_field.value.strip() or "0.25in",
            "center_headings": center_headings_switch.value,
            "bold_headings": bold_headings_switch.value,
            "paragraph_spacing": paragraph_spacing_dd.value,
            "include_toc": include_toc_switch.value,
            "beautify_toc": beautify_toc_switch.value,
            "toc_language": toc_language_dd.value,
            "toc_alignment": toc_alignment_dd.value,
            "toc_design": toc_design_dd.value,
            "page_border": page_border_switch.value,
            "hyphenation": hyphenation_switch.value,
            "line_height": line_height_dd.value,
            "copy_friendly_text": False,
            "output_name": output_name_field.value.strip(),
            "output_directory": output_dir_val[0],
        }

    def apply_settings(settings):
        if not settings or not isinstance(settings, dict):
            return
        if "theme_mode" in settings:
            try:
                page.theme_mode = ft.ThemeMode(settings["theme_mode"])
            except ValueError:
                page.theme_mode = ft.ThemeMode.SYSTEM
            update_theme_button()
            refresh_preview()
        if "page_size_choice" in settings and settings["page_size_choice"] in PAGE_SIZES:
            page_size_dropdown.value = settings["page_size_choice"]
        if "orientation" in settings:
            orientation_dropdown.value = settings["orientation"]
        if "margin_choice" in settings:
            margin_dropdown.value = settings["margin_choice"]
        if "custom_margin" in settings:
            custom_margin_field.value = settings["custom_margin"]
        if "font_size_choice" in settings:
            font_size_dd.value = settings["font_size_choice"]
        if "custom_font_size" in settings:
            custom_font_size_field.value = str(settings["custom_font_size"])
        if "english_font" in settings:
            english_font_dd.value = settings["english_font"]
        if "heading_font" in settings:
            heading_font_dd.value = settings["heading_font"]
        if "bengali_font" in settings:
            bengali_font_dd.value = settings["bengali_font"]
        if "arabic_font" in settings:
            arabic_font_dd.value = settings["arabic_font"]
        if "page_numbers" in settings:
            page_numbers_switch.value = bool(settings["page_numbers"])
        if "page_number_position" in settings:
            page_number_position_dd.value = settings["page_number_position"]
        if "page_number_format" in settings:
            page_number_format_dd.value = settings["page_number_format"]
        if "page_number_language" in settings:
            page_number_language_dd.value = settings["page_number_language"]
        if "indent_first_line" in settings:
            indent_switch.value = bool(settings["indent_first_line"])
        if "indent_amount" in settings:
            indent_amount_field.value = settings["indent_amount"]
        if "center_headings" in settings:
            center_headings_switch.value = bool(settings["center_headings"])
        if "bold_headings" in settings:
            bold_headings_switch.value = bool(settings["bold_headings"])
        if "paragraph_spacing" in settings:
            paragraph_spacing_dd.value = settings["paragraph_spacing"]
        if "include_toc" in settings:
            include_toc_switch.value = bool(settings["include_toc"])
        if "beautify_toc" in settings:
            beautify_toc_switch.value = bool(settings["beautify_toc"])
        if "toc_language" in settings:
            toc_language_dd.value = settings["toc_language"]
        if "toc_alignment" in settings:
            toc_alignment_dd.value = settings["toc_alignment"]
        if "toc_design" in settings:
            toc_design_dd.value = settings["toc_design"]
        if "page_border" in settings:
            page_border_switch.value = bool(settings["page_border"])
        if "hyphenation" in settings:
            hyphenation_switch.value = bool(settings["hyphenation"])
        if "line_height" in settings:
            line_height_dd.value = str(settings["line_height"])
        page.update()

    def handle_load_profile(e):
        name = profile_dropdown.value
        all_profs = load_profiles()
        if name in all_profs:
            apply_settings(all_profs[name])
            save_last_used_settings(collect_current_settings(), selected_profile=name)
            append_log(f"[PROFILE] Loaded preset '{name}' successfully.")

    def handle_save_profile(e):
        name = save_profile_field.value.strip()
        if not name:
            append_log("[ERROR] Please enter a profile name.")
            return
        try:
            curr = collect_current_settings()
            save_profile(name, curr)
            append_log(f"[PROFILE] Saved profile '{name}'.")
            save_profile_field.value = ""
            all_profs = load_profiles()
            profile_names = [profile_name for profile_name in all_profs if profile_name != LAST_USED_PROFILE]
            profile_dropdown.options = [ft.dropdown.Option(profile_name) for profile_name in profile_names]
            profile_dropdown.value = name
            update_profile_btn.disabled = False
            save_last_used_settings(curr, selected_profile=name)
            page.update()
        except Exception as ex:
            append_log(f"[ERROR] Could not save profile: {ex}")

    def handle_update_profile(e):
        name = profile_dropdown.value
        if not is_profile_selected(name):
            append_log("[ERROR] Select a profile to update.")
            return
        try:
            update_profile(name, collect_current_settings())
            save_last_used_settings(collect_current_settings(), selected_profile=name)
            append_log(f"[PROFILE] Updated profile '{name}'.")
        except Exception as ex:
            append_log(f"[ERROR] Could not update profile: {ex}")

    def handle_profile_selection_change(e):
        update_profile_btn.disabled = not is_profile_selected(profile_dropdown.value)
        save_last_used_settings(collect_current_settings(), selected_profile=profile_dropdown.value)
        page.update()

    profile_dropdown.on_change = handle_profile_selection_change
    update_profile_btn = ft.OutlinedButton(
        "Update Selected",
        icon=ft.Icons.SAVE,
        disabled=not is_profile_selected(profile_dropdown.value),
        on_click=handle_update_profile,
    )

    def handle_delete_profile(e):
        name = profile_dropdown.value
        if not name:
            return
        if name in BUILT_IN_PROFILES:
            append_log(f"[ERROR] Built-in profile '{name}' cannot be deleted.")
            return
        if delete_profile(name):
            append_log(f"[PROFILE] Deleted profile '{name}'.")
            all_profs = load_profiles()
            profile_names = [profile_name for profile_name in all_profs if profile_name != LAST_USED_PROFILE]
            profile_dropdown.options = [ft.dropdown.Option(profile_name) for profile_name in profile_names]
            profile_dropdown.value = profile_names[0] if profile_names else None
            update_profile_btn.disabled = not is_profile_selected(profile_dropdown.value)
            save_last_used_settings(collect_current_settings(), selected_profile=profile_dropdown.value)
            page.update()

    profiles_tab = ft.Container(
        content=ft.Column(
            [
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Configuration Profiles", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row(
                                    [
                                        profile_dropdown,
                                        ft.FilledTonalButton("Apply Profile", icon=ft.Icons.CHECK, on_click=handle_load_profile),
                                        update_profile_btn,
                                        ft.OutlinedButton("Delete", icon=ft.Icons.DELETE_OUTLINE, on_click=handle_delete_profile),
                                    ],
                                    spacing=12,
                                ),
                                ft.Divider(),
                                ft.Text("Save Current Configuration:", weight=ft.FontWeight.W_500),
                                ft.Row(
                                    [
                                        save_profile_field,
                                        ft.FilledButton("Save as New", icon=ft.Icons.SAVE, on_click=handle_save_profile),
                                    ],
                                    spacing=12,
                                ),
                            ],
                            spacing=14,
                        ),
                        padding=16,
                    )
                )
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=10,
    )

    # ---------------- Editor Tab ----------------
    editor_file_path = [None]
    editor_dirty = [False]
    last_editor_selection = [None]
    format_buttons = []
    # Editor/preview split: the editor takes ``editor_flex`` of the row and the
    # preview pane (when visible) takes the rest. The divider in between is
    # draggable to resize both panes.
    EDITOR_MIN_FLEX = 3
    EDITOR_MAX_FLEX = 7
    editor_flex = [5.0]
    preview_open = [False]

    def refresh_editor_status():
        name = Path(editor_file_path[0]).name if editor_file_path[0] else "Untitled"
        mode = editor_mode_dd.value or "Markdown"
        if editor_dirty[0]:
            editor_status.value = f"{name}  |  {mode}  •  unsaved changes"
            editor_status.color = ft.Colors.AMBER_400
        else:
            editor_status.value = f"{name}  |  {mode}"
            editor_status.color = ft.Colors.GREY_400

    def handle_editor_change(_e):
        if not editor_dirty[0]:
            editor_dirty[0] = True
            refresh_editor_status()
        refresh_preview()
        page.update()

    def handle_selection_change(e):
        try:
            last_editor_selection[0] = (e.selection.start, e.selection.end)
        except AttributeError:
            last_editor_selection[0] = None

    def handle_editor_mode_change(_e):
        plain = editor_mode_dd.value == "Plain Text"
        for button in format_buttons:
            button.disabled = plain
        refresh_editor_status()
        refresh_preview()
        page.update()

    def apply_transform(producer):
        value = editor_field.value or ""
        selection = editor_field.selection
        if selection is not None:
            start, end = selection.start, selection.end
        elif last_editor_selection[0] is not None:
            start, end = last_editor_selection[0]
        else:
            start = end = len(value)
        if start > end:
            start, end = end, start
        new_value, new_start, new_end = producer(value, start, end)
        editor_field.value = new_value
        editor_field.selection = ft.TextSelection(new_start, new_end)
        last_editor_selection[0] = (new_start, new_end)
        if not editor_dirty[0]:
            editor_dirty[0] = True
            refresh_editor_status()
        page.run_task(editor_field.focus)
        refresh_preview()
        page.update()

    def format_button(icon, tooltip, producer):
        button = ft.IconButton(
            icon=icon,
            tooltip=tooltip,
            icon_size=18,
            width=32,
            height=32,
            style=ft.ButtonStyle(padding=0),
            on_click=lambda _e, action=producer: apply_transform(action),
        )
        format_buttons.append(button)
        return button

    def editor_extension():
        return ".txt" if editor_mode_dd.value == "Plain Text" else ".md"

    def write_editor_buffer(target):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(editor_field.value or "", encoding="utf-8")

    def save_editor_buffer():
        if not editor_file_path[0]:
            return False
        try:
            write_editor_buffer(editor_file_path[0])
        except OSError as error:
            append_log(f"[ERROR] Could not save the editor document: {error}")
            return False
        editor_dirty[0] = False
        refresh_editor_status()
        append_log(f"[EDITOR] Saved '{Path(editor_file_path[0]).name}'.")
        page.update()
        return True

    def write_session_buffer():
        directory = Path(tempfile.gettempdir()) / "pdf-creator-studio"
        target = directory / f"editor-draft{editor_extension()}"
        write_editor_buffer(target)
        return target

    async def handle_save_as(_e=None):
        chosen = await file_picker.save_file(
            dialog_title="Save Editor Document",
            file_name=f"untitled{editor_extension()}",
            allowed_extensions=["md", "markdown", "txt"],
        )
        if not chosen:
            return
        if not Path(chosen).suffix:
            chosen += editor_extension()
        editor_file_path[0] = chosen
        save_editor_buffer()

    async def handle_save_click(_e=None):
        if editor_file_path[0]:
            save_editor_buffer()
        else:
            await handle_save_as(None)

    async def handle_open_in_editor(_e=None):
        picked = await file_picker.pick_files(
            dialog_title="Open Document in Editor",
            allowed_extensions=["md", "markdown", "txt"],
        )
        if not picked:
            return
        path = picked[0].path
        try:
            content = Path(path).read_text(encoding="utf-8-sig")
        except OSError as error:
            append_log(f"[ERROR] Could not open '{path}': {error}")
            return
        editor_field.value = content
        editor_field.selection = None
        editor_file_path[0] = path
        editor_dirty[0] = False
        editor_mode_dd.value = (
            "Plain Text" if Path(path).suffix.lower() == ".txt" else "Markdown"
        )
        handle_editor_mode_change(None)
        append_log(f"[EDITOR] Opened '{Path(path).name}' in the editor.")
        page.update()

    async def execute_editor_conversion(_e=None):
        content = editor_field.value or ""
        if not content.strip():
            append_log("[ERROR] The editor is empty - nothing to convert.")
            return
        if editor_file_path[0]:
            if not save_editor_buffer():
                return
            buffer_path = Path(editor_file_path[0])
            default_output_name = buffer_path.stem
        else:
            buffer_path = write_session_buffer()
            default_output_name = "Editor Draft"
            append_log(
                "[EDITOR] Converted from a temporary buffer. Use Save As to keep a copy on disk."
            )
        extra_options = {}
        if editor_mode_dd.value == "Plain Text":
            extra_options["input_format"] = "plain"
        await run_conversion(
            [str(buffer_path)],
            default_output_name=default_output_name,
            extra_options=extra_options,
        )

    editor_mode_dd = ft.Dropdown(
        label="Format",
        value="Markdown",
        options=[ft.dropdown.Option("Markdown"), ft.dropdown.Option("Plain Text")],
        width=150,
        dense=True,
        on_select=handle_editor_mode_change,
    )
    editor_status = ft.Text(
        value="Untitled  |  Markdown",
        size=12,
        color=ft.Colors.GREY_400,
    )
    editor_field = ft.TextField(
        multiline=True,
        fit_parent_size=True,
        expand=True,
        value="",
        hint_text="Paste or type Markdown or plain text here, then convert it directly to PDF.",
        text_style=ft.TextStyle(font_family="monospace"),
        text_size=14,
        border={
            ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                border_radius=8,
                side=ft.BorderSide(1.5, ft.Colors.OUTLINE),
            ),
            ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                border_radius=8,
                side=ft.BorderSide(2, ft.Colors.PRIMARY),
            ),
        },
        filled=True,
        fill_color=ft.Colors.SURFACE,
        cursor_color=ft.Colors.PRIMARY,
        autofocus=True,
        on_change=handle_editor_change,
        on_selection_change=handle_selection_change,
    )
    # ---------------- Live Markdown Preview ----------------
    def render_preview():
        """Rebuild the preview pane from the current editor buffer."""
        if editor_mode_dd.value == "Plain Text":
            preview_body.controls = [
                ft.Text(
                    editor_field.value or "Nothing to preview yet.",
                    size=14,
                    selectable=True,
                )
            ]
        elif not (editor_field.value or "").strip():
            preview_body.controls = [
                ft.Text(
                    "Nothing to preview yet. Start typing in the editor.",
                    size=13,
                    italic=True,
                    color=ft.Colors.GREY_400,
                )
            ]
        else:
            preview_body.controls = markdown_to_controls(
                editor_field.value,
                dark_theme=not is_light_theme(),
            )

    def refresh_preview():
        if preview_open[0]:
            render_preview()

    def apply_editor_split():
        """Apply the flex split between the editor and the preview pane."""
        editor_pane.expand = round(editor_flex[0] * 100)
        preview_pane.expand = 1000 - editor_pane.expand

    def resize_editor_split(e):
        # Dragging the divider right grows the editor pane, left shrinks it.
        # NOTE: Flet 1.x removed the flat ``delta_x``/``delta_y`` attributes from
        # DragUpdateEvent. For a horizontal-drag handler the movement since the
        # previous update is reported via ``primary_delta`` (``None`` for
        # proxied events such as accessibility), so fall back to 0.
        delta_x = e.primary_delta or 0
        editor_flex[0] = max(
            EDITOR_MIN_FLEX,
            min(EDITOR_MAX_FLEX, editor_flex[0] + delta_x * 10 / max((page.width or 1180) - 80, 1)),
        )
        apply_editor_split()
        page.update()

    def update_editor_layout():
        """Show or hide the preview pane and divider next to the editor."""
        if preview_open[0]:
            editor_split_row.controls = [editor_pane, split_divider, preview_pane]
        else:
            editor_split_row.controls = [editor_pane]
        preview_toggle_btn.icon = (
            ft.Icons.VISIBILITY_OFF_OUTLINED if preview_open[0] else ft.Icons.VISIBILITY_OUTLINED
        )
        preview_toggle_btn.tooltip = (
            "Hide Markdown preview" if preview_open[0] else "Show Markdown preview"
        )
        apply_editor_split()

    def toggle_preview(_e=None):
        preview_open[0] = not preview_open[0]
        update_editor_layout()
        if preview_open[0]:
            render_preview()
        page.update()

    preview_toggle_btn = ft.IconButton(
        icon=ft.Icons.VISIBILITY_OUTLINED,
        tooltip="Show Markdown preview",
        on_click=toggle_preview,
    )

    preview_title = ft.Text("Markdown Preview", weight=ft.FontWeight.BOLD, size=13)
    preview_body = ft.Column(
        [
            ft.Text(
                "Nothing to preview yet. Start typing in the editor.",
                size=13,
                italic=True,
                color=ft.Colors.GREY_400,
            )
        ],
        spacing=8,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    def _close_preview(_e=None):
        if preview_open[0]:
            toggle_preview(_e)

    close_preview_btn = ft.IconButton(
        icon=ft.Icons.CLOSE,
        icon_size=18,
        width=32,
        height=32,
        tooltip="Close preview",
        on_click=_close_preview,
    )
    preview_pane = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [preview_title, ft.Container(expand=True), close_preview_btn],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                ft.Divider(height=6),
                preview_body,
            ],
            spacing=6,
            expand=True,
        ),
        padding=ft.Padding(left=12, top=0, right=0, bottom=0),
        expand=500,
    )
    split_divider = ft.GestureDetector(
        content=ft.Container(
            content=ft.VerticalDivider(width=14, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
            width=14,
        ),
        drag_interval=1,
        on_horizontal_drag_update=resize_editor_split,
        mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
    )
    editor_pane = ft.Container(
        content=editor_field,
        expand=500,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )
    editor_split_row = ft.Row(
        [editor_pane],
        expand=True,
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # ---------------- Clear / Close current file ----------------
    def _do_clear_editor():
        editor_field.value = ""
        editor_field.selection = None
        editor_file_path[0] = None
        editor_dirty[0] = False
        last_editor_selection[0] = None
        editor_mode_dd.value = "Markdown"
        handle_editor_mode_change(None)
        refresh_editor_status()
        refresh_preview()
        append_log("[EDITOR] Editor cleared and file closed.")
        page.update()

    def _dismiss_clear_dialog(_e=None):
        # Flet 1.x dialogs are managed by the page's internal dialog stack.
        # Close programmatically with pop_dialog() instead of toggling
        # ``open``/overlay by hand - the legacy pattern never signals Flutter
        # to dismiss the dialog, so it stayed on screen. Only pop if our
        # dialog is the one currently open.
        if clear_editor_dialog.open:
            page.pop_dialog()
        page.update()

    def _confirm_clear_editor(_e=None):
        _dismiss_clear_dialog()
        _do_clear_editor()

    clear_editor_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Clear editor?"),
        content=ft.Text(
            "The editor has unsaved changes. Clear the editor and close the current "
            "file anyway? This cannot be undone."
        ),
        actions=[
            ft.TextButton("Cancel", on_click=_dismiss_clear_dialog),
            ft.FilledButton("Clear anyway", on_click=_confirm_clear_editor),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def handle_clear_editor(_e=None):
        if editor_dirty[0] or editor_file_path[0]:
            # Flet 1.x: show_dialog() registers the dialog with the page's
            # dialog stack and wires up dismissal cleanup. It raises if the
            # dialog is already open, so guard first.
            if not clear_editor_dialog.open:
                page.show_dialog(clear_editor_dialog)
            page.update()
        else:
            append_log("[EDITOR] The editor is already empty.")
            page.update()

    # ---------------- Expand / restore window ----------------
    def toggle_window_maximize(_e=None):
        """Toggle the window between maximized and its previous size."""
        page.window.maximized = not page.window.maximized
        expand_editor_btn.icon = (
            ft.Icons.FULLSCREEN_EXIT if page.window.maximized else ft.Icons.FULLSCREEN
        )
        expand_editor_btn.tooltip = (
            "Restore window size" if page.window.maximized else "Maximize the window"
        )
        page.update()

    expand_editor_btn = ft.IconButton(
        icon=ft.Icons.FULLSCREEN,
        icon_size=20,
        width=32,
        height=32,
        tooltip="Maximize the window",
        on_click=toggle_window_maximize,
    )

    editor_toolbar = ft.Row(
        [
            format_button(ft.Icons.FORMAT_BOLD, "Bold", bold_producer()),
            format_button(ft.Icons.FORMAT_ITALIC, "Italic", italic_producer()),
            format_button(
                ft.Icons.FORMAT_STRIKETHROUGH,
                "Strikethrough",
                strikethrough_producer(),
            ),
            format_button(ft.Icons.LOOKS_ONE, "Heading level 1", heading_producer(1)),
            format_button(ft.Icons.LOOKS_TWO, "Heading level 2", heading_producer(2)),
            format_button(ft.Icons.LOOKS_3, "Heading level 3", heading_producer(3)),
            format_button(
                ft.Icons.FORMAT_LIST_BULLETED, "Bulleted list", bullet_producer()
            ),
            format_button(
                ft.Icons.FORMAT_LIST_NUMBERED, "Numbered list", ordered_list_producer()
            ),
            format_button(ft.Icons.FORMAT_QUOTE, "Block quote", quote_producer()),
            format_button(ft.Icons.CODE, "Inline code", inline_code_producer()),
            format_button(ft.Icons.DATA_OBJECT, "Code block", code_block_producer()),
            format_button(ft.Icons.LINK, "Insert link", link_producer()),
            format_button(
                ft.Icons.HORIZONTAL_RULE, "Horizontal rule", horizontal_rule_producer()
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
        spacing=2,
    )
    editor_convert_btn = ft.FilledButton(
        "Export PDF",
        icon=ft.Icons.ROCKET_LAUNCH,
        on_click=execute_editor_conversion,
    )

    editor_tab = ft.Container(
        expand=True,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.FILE_OPEN,
                            tooltip="Open document",
                            on_click=handle_open_in_editor,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.SAVE, tooltip="Save", on_click=handle_save_click
                        ),
                        ft.IconButton(
                            icon=ft.Icons.SAVE_AS,
                            tooltip="Save As...",
                            on_click=handle_save_as,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            tooltip="Clear the editor and close the current file",
                            on_click=handle_clear_editor,
                        ),
                        ft.Container(content=editor_status, expand=True),
                        editor_mode_dd,
                        preview_toggle_btn,
                        expand_editor_btn,
                        editor_convert_btn,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                ),
                editor_toolbar,
                editor_split_row,
            ],
            spacing=6,
            expand=True,
        ),
        padding=ft.Padding(left=4, top=4, right=4, bottom=0),
    )

    # ---------------- Bottom Status, Console & Actions ----------------
    log_messages = []
    log_column = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=4, auto_scroll=True)

    async def copy_log(_e):
        await clipboard.set("\n".join(log_messages))

    log_expanded = [False]

    def set_log_expanded(expanded):
        log_expanded[0] = expanded
        log_column.visible = expanded
        log_container.height = 160 if expanded else 48
        log_container.padding = 10 if expanded else 4
        log_toggle_btn.icon = ft.Icons.EXPAND_LESS if expanded else ft.Icons.EXPAND_MORE
        log_toggle_btn.tooltip = "Collapse conversion log" if expanded else "Expand conversion log"

    def toggle_log(_e=None):
        set_log_expanded(not log_expanded[0])
        page.update()

    log_toggle_btn = ft.IconButton(
        icon=ft.Icons.EXPAND_MORE,
        tooltip="Expand conversion log",
        on_click=toggle_log,
    )

    log_header = ft.Row(
        [
            ft.Text("Conversion Log", weight=ft.FontWeight.BOLD),
            ft.IconButton(
                icon=ft.Icons.CONTENT_COPY,
                tooltip="Copy log",
                on_click=copy_log,
            ),
            log_toggle_btn,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    log_copy_button = log_header.controls[1]
    log_container = ft.Container(
        content=ft.Column([log_header, log_column], expand=True, spacing=4),
        height=160,
        border_radius=8,
        padding=10,
    )

    def log_entry_color(message):
        light_mode = page.theme_mode == ft.ThemeMode.LIGHT or (
            page.theme_mode == ft.ThemeMode.SYSTEM
            and page.platform_brightness == ft.Brightness.LIGHT
        )
        if "[SUCCESS]" in message:
            return "#18733B" if light_mode else ft.Colors.GREEN_400
        if "[ERROR]" in message or "[EXCEPTION]" in message:
            return "#B42318" if light_mode else ft.Colors.RED_400
        if "[CHANGE DETECTED]" in message or "[PROFILE]" in message:
            return "#087E8B" if light_mode else ft.Colors.CYAN_400
        return "#202124" if light_mode else ft.Colors.WHITE

    def apply_log_theme():
        light_mode = page.theme_mode == ft.ThemeMode.LIGHT or (
            page.theme_mode == ft.ThemeMode.SYSTEM
            and page.platform_brightness == ft.Brightness.LIGHT
        )
        log_container.bgcolor = "#F1F3F5" if light_mode else ft.Colors.BLACK
        log_header.controls[0].color = "#202124" if light_mode else ft.Colors.WHITE
        log_copy_button.icon_color = "#202124" if light_mode else ft.Colors.WHITE
        for control in log_column.controls:
            control.color = log_entry_color(control.value)

    page.on_platform_brightness_change = handle_platform_brightness_change

    def append_log(message):
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        log_messages.append(formatted_message)
        log_column.controls.append(
            ft.Text(formatted_message, size=12, font_family="monospace", color=log_entry_color(message), selectable=True)
        )
        page.update()

    status_badge = ft.Text("Status: Ready", weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400)
    progress_bar = ft.ProgressBar(visible=False, color=ft.Colors.AMBER_400)

    mode_segmented = ft.SegmentedButton(
        selected=["once"],
        segments=[
            ft.Segment(value="once", label=ft.Text("Convert Once"), icon=ft.Icon(ft.Icons.FLASH_ON)),
            ft.Segment(value="auto", label=ft.Text("Auto-Convert (Watch)"), icon=ft.Icon(ft.Icons.SYNC)),
        ],
    )

    open_pdf_btn = ft.OutlinedButton(
        "Open Generated PDF",
        icon=ft.Icons.PICTURE_AS_PDF,
        disabled=True,
        on_click=lambda e: open_in_system(last_converted_pdf[0]) if last_converted_pdf[0] else None,
    )

    async def run_conversion(files, default_output_name=None, extra_options=None):
        settings = collect_current_settings()
        save_last_used_settings(settings, selected_profile=profile_dropdown.value)
        progress_bar.visible = True
        action_btn.disabled = True
        editor_convert_btn.disabled = True
        status_badge.value = "Status: Converting..."
        status_badge.color = ft.Colors.AMBER_400
        page.update()

        conversion_options = dict(extra_options or {})
        conversion_options.update(
            {
                "page_size_choice": settings["page_size_choice"],
                "font_size_choice": settings["font_size_choice"],
                "custom_font_size": settings["custom_font_size"],
                "output_name": settings["output_name"] or default_output_name,
                "output_directory": settings["output_directory"],
                "english_font": settings["english_font"],
                "heading_font": settings["heading_font"],
                "bengali_font": settings["bengali_font"],
                "arabic_font": settings["arabic_font"],
                "margin_choice": settings["margin_choice"],
                "custom_margin": settings["custom_margin"],
                "orientation": settings["orientation"],
                "page_numbers": settings["page_numbers"],
                "page_number_style": settings["page_number_style"],
                "page_number_format": settings["page_number_format"],
                "page_number_position": settings["page_number_position"],
                "page_number_size": settings["page_number_size"],
                "page_number_language": settings["page_number_language"],
                "indent_first_line": settings["indent_first_line"],
                "indent_amount": settings["indent_amount"],
                "paragraph_spacing": settings["paragraph_spacing"],
                "center_headings": settings["center_headings"],
                "bold_headings": settings["bold_headings"],
                "include_toc": settings["include_toc"],
                "beautify_toc": settings["beautify_toc"],
                "toc_language": settings["toc_language"],
                "toc_alignment": settings["toc_alignment"],
                "toc_design": settings["toc_design"],
                "page_border": settings["page_border"],
                "hyphenation": settings["hyphenation"],
                "line_height": settings["line_height"],
                "copy_friendly_text": settings["copy_friendly_text"],
                "highlight_style": "breezedark" if not is_light_theme() else "tango",
            }
        )

        def run_sync():
            return convert_many_to_pdf(
                files,
                log_func=append_log,
                **conversion_options,
            )

        results = await asyncio.to_thread(run_sync)
        progress_bar.visible = False
        action_btn.disabled = False
        editor_convert_btn.disabled = False

        succeeded = [res for _src, succ, res in results if succ]
        if succeeded:
            last_converted_pdf[0] = succeeded[0]
            open_pdf_btn.disabled = False
            status_badge.value = f"Status: Succeeded ({len(succeeded)}/{len(results)} files)"
            status_badge.color = ft.Colors.GREEN_400
        else:
            status_badge.value = "Status: Conversion Failed"
            status_badge.color = ft.Colors.RED_400
        page.update()

    async def execute_conversion():
        if not selected_files:
            append_log("[ERROR] No input document selected.")
            return
        await run_conversion(list(selected_files))

    async def toggle_watch_mode():
        if is_watching[0]:
            is_watching[0] = False
            action_btn.text = "🚀 Start Conversion"
            action_btn.icon = ft.Icons.ROCKET_LAUNCH
            status_badge.value = "Status: Watch Mode Stopped"
            status_badge.color = ft.Colors.GREY_400
            append_log("[WATCH] Auto-convert stopped.")
            page.update()
            return

        if len(selected_files) != 1 or not Path(selected_files[0]).exists():
            append_log("[ERROR] Auto-convert requires exactly one valid document.")
            return

        target_file = selected_files[0]
        is_watching[0] = True
        action_btn.text = "⏹ Stop Auto-Convert"
        action_btn.icon = ft.Icons.STOP
        status_badge.value = f"Status: Watching '{Path(target_file).name}'"
        status_badge.color = ft.Colors.CYAN_400
        append_log(f"[WATCH] Auto-convert started on '{Path(target_file).name}'. Monitoring changes...")
        page.update()

        settings = collect_current_settings()
        save_last_used_settings(settings, selected_profile=profile_dropdown.value)

        # Initial compile
        await execute_conversion()

        async def watch_loop():
            last_mtime = Path(target_file).stat().st_mtime
            while is_watching[0]:
                await asyncio.sleep(2)
                if not Path(target_file).exists():
                    continue
                cur_mtime = Path(target_file).stat().st_mtime
                if cur_mtime != last_mtime:
                    last_mtime = cur_mtime
                    append_log(f"[CHANGE DETECTED] File updated at {time.strftime('%H:%M:%S')}. Re-compiling...")
                    await execute_conversion()

        watch_task[0] = asyncio.create_task(watch_loop())

    async def handle_action_click(e):
        mode = list(mode_segmented.selected)[0] if mode_segmented.selected else "once"
        if mode == "auto":
            await toggle_watch_mode()
        else:
            await execute_conversion()

    action_btn = ft.FilledButton(
        "🚀 Convert to PDF",
        icon=ft.Icons.ROCKET_LAUNCH,
        on_click=handle_action_click,
        style=ft.ButtonStyle(padding=18),
    )

    # ---------------- Help Tab ----------------
    help_selected_topic = [None]
    help_search_field = ft.TextField(
        label="Search help topics",
        hint_text="Type to filter topics, e.g. 'preview', 'fonts', 'toc'",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
        # Deferred so the handler can be defined after the control.
        on_change=lambda e: handle_help_search(e),
    )
    help_results_count = ft.Text("", size=12, color=ft.Colors.GREY_400)
    help_topic_list = ft.Column(spacing=2, expand=True, scroll=ft.ScrollMode.AUTO)
    help_topic_content = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)

    def render_help_list(matches):
        help_topic_list.controls = [help_topic_card(topic) for topic in matches]

    def render_help_topic(topic):
        help_selected_topic[0] = topic["title"] if topic else None
        help_topic_content.controls = (
            markdown_to_controls(topic["body"], dark_theme=not is_light_theme())
            if topic
            else [
                ft.Text(
                    "Select a topic on the left, or search for a keyword.",
                    italic=True,
                    color=ft.Colors.GREY_400,
                )
            ]
        )

    def handle_help_search(_e=None):
        matches = search_help_topics(help_search_field.value)
        help_results_count.value = (
            f"{len(matches)} topic{'s' if len(matches) != 1 else ''} found"
        )
        render_help_list(matches)
        if help_selected_topic[0] not in {topic["title"] for topic in matches}:
            render_help_topic(matches[0] if matches else None)
        else:
            render_help_topic(
                next(
                    (topic for topic in matches if topic["title"] == help_selected_topic[0]),
                    None,
                )
            )
        page.update()

    def help_topic_card(topic):
        selected = topic["title"] == help_selected_topic[0]
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(topic["title"], weight=ft.FontWeight.W_600, size=13),
                        ft.Text(
                            topic["summary"],
                            size=12,
                            color=ft.Colors.GREY_400,
                        ),
                    ],
                    spacing=2,
                    tight=True,
                ),
                padding=10,
                data=topic["title"],
                on_click=lambda _e, t=topic: _select_help_topic(t),
                ink=True,
                bgcolor=ft.Colors.BLUE_900 if selected else None,
            ),
            margin=ft.Margin(bottom=4, left=0, right=0, top=0),
        )

    def _select_help_topic(topic):
        render_help_topic(topic)
        render_help_list(search_help_topics(help_search_field.value))
        page.update()

    render_help_list(HELP_TOPICS)
    render_help_topic(HELP_TOPICS[0])
    help_results_count.value = f"{len(HELP_TOPICS)} topics found"

    help_tab = ft.Container(
        expand=True,
        content=ft.Column(
            [
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Help", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row(
                                    [help_search_field, help_results_count],
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=12,
                                ),
                            ],
                            spacing=10,
                        ),
                        padding=16,
                    )
                ),
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Topics",
                                        weight=ft.FontWeight.W_600,
                                        size=13,
                                    ),
                                    ft.Divider(height=4),
                                    help_topic_list,
                                ],
                                spacing=4,
                                expand=True,
                            ),
                            width=260,
                            expand=True,
                        ),
                        ft.VerticalDivider(width=1, thickness=1),
                        ft.Container(
                            content=help_topic_content,
                            expand=True,
                            padding=ft.Padding(left=12, top=0, right=0, bottom=0),
                        ),
                    ],
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    spacing=8,
                ),
            ],
            spacing=12,
            expand=True,
        ),
        padding=10,
    )

    # ---------------- Assemble Tabs ----------------
    tab_bar = ft.TabBar(
        tabs=[
            ft.Tab(label="Editor", icon=ft.Icons.EDIT_OUTLINED),
            ft.Tab(label="Documents", icon=ft.Icons.DESCRIPTION_OUTLINED),
            ft.Tab(label="Page & Geometry", icon=ft.Icons.ASPECT_RATIO),
            ft.Tab(label="Typography", icon=ft.Icons.FONT_DOWNLOAD_OUTLINED),
            ft.Tab(label="TOC & Numbers", icon=ft.Icons.FORMAT_LIST_NUMBERED),
            ft.Tab(label="Profiles", icon=ft.Icons.BOOKMARKS_OUTLINED),
            ft.Tab(label="Help", icon=ft.Icons.HELP_OUTLINE),
        ]
    )

    tab_views = ft.TabBarView(
        expand=True,
        controls=[
            editor_tab,
            files_tab,
            geometry_tab,
            typography_tab,
            toc_tab,
            profiles_tab,
            help_tab,
        ],
    )

    def handle_tab_change(_e):
        set_log_expanded(tabs.selected_index != 0)
        page.update()

    tabs = ft.Tabs(
        length=7,
        selected_index=0,
        on_change=handle_tab_change,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                tab_bar,
                tab_views,
            ],
        ),
    )

    set_log_expanded(False)

    # Main view structure
    page.add(
        tabs,
        ft.Divider(),
        ft.Row(
            [
                status_badge,
                ft.Container(expand=True),
                mode_segmented,
                open_pdf_btn,
                action_btn,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        progress_bar,
        log_container,
    )

    if last_used_settings:
        apply_settings(last_used_settings)
    apply_log_theme()

    append_log("[STUDIO] PDF Creator Studio initialized.")
    append_log(f"[STUDIO] Project root: {Path(INPUT_DIR).parent.name}")


def launch_flet_app():
    """Launch the modern Material 3 desktop application."""
    ft.run(main)


if __name__ == "__main__":
    launch_flet_app()
