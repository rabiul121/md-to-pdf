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
    INPUT_DIR,
    OUTPUT_DIR,
    SUPPORTED_INPUT_EXTENSIONS,
    PAGE_SIZES,
    PAGE_DEFAULT_MARGINS,
    MARGIN_PRESETS,
    FONT_SIZES,
    PROJECT_FONT_CHOICES,
    HEADING_FONT_CHOICES,
    CODING_FONT_CHOICES,
    BASE_DIR,
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
    continue_markdown_block,
    heading_producer,
    horizontal_rule_producer,
    inline_code_producer,
    italic_producer,
    link_producer,
    ordered_list_producer,
    quote_producer,
    strikethrough_producer,
    task_list_producer,
)
from src.core.markdown_preview import markdown_to_controls
from src.core.help_topics import HELP_TOPICS, search_help_topics


def resolve_theme_mode(value=None):
    """Resolve a persisted theme value, falling back to System mode."""
    if value is None:
        return ft.ThemeMode.SYSTEM
    try:
        return ft.ThemeMode(value)
    except ValueError:
        return ft.ThemeMode.SYSTEM


async def main(page: ft.Page):
    last_used_settings = load_last_used_settings()
    initial_theme_mode = resolve_theme_mode(
        last_used_settings.get("theme_mode", ft.ThemeMode.SYSTEM.value)
    )

    page.title = "PDF Creator Studio"
    page.window.width = 1180
    page.window.height = 860
    page.window.min_width = 800
    page.window.min_height = 680
    page.theme_mode = initial_theme_mode
    page.padding = 16
    page.fonts = {
        "JetBrains Mono": (BASE_DIR / "assets" / "fonts" / "english" / "JetBrainsMono-VariableFont_wght.ttf").as_posix(),
    }
    for family, filename in (
        ("MonoLisa", "MonoLisa-Regular.ttf"),
        ("Operator Mono", "OperatorMono-Book.ttf"),
    ):
        font_path = BASE_DIR / "assets" / "fonts" / "coading" / filename
        if font_path.is_file():
            page.fonts[family] = font_path.as_posix()

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
    active_view = ["editor"]
    sidebar_expanded = [True]
    preferences_expanded = [True]

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

    # Conversion-log utility controls. The log itself is shared by the Editor
    # and Documents views, but each view keeps its own top-right copy/fold
    # cluster so the controls always sit beside the window expand button.
    log_toggle_buttons = []
    log_copy_buttons = []

    async def handle_log_copy(_e):
        # Flet must receive an async handler directly; wrapping an async
        # callback in a lambda can leave its coroutine unawaited.
        await copy_log(_e)

    def make_log_toggle_button():
        button = ft.IconButton(
            icon=ft.Icons.EXPAND_MORE,
            tooltip="Expand conversion log",
            on_click=lambda _e: toggle_log(_e),
        )
        log_toggle_buttons.append(button)
        return button

    def make_log_copy_button():
        button = ft.IconButton(
            icon=ft.Icons.CONTENT_COPY,
            tooltip="Copy log",
            on_click=handle_log_copy,
        )
        log_copy_buttons.append(button)
        return button

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

    render_sidebar_fn = [None]

    def toggle_theme(e):
        theme_cycle = (ft.ThemeMode.SYSTEM, ft.ThemeMode.LIGHT, ft.ThemeMode.DARK)
        current_index = theme_cycle.index(page.theme_mode)
        page.theme_mode = theme_cycle[(current_index + 1) % len(theme_cycle)]
        update_theme_button()
        apply_log_theme()
        if render_sidebar_fn[0]:
            render_sidebar_fn[0]()
        refresh_preview()
        save_last_used_settings(
            collect_current_settings(),
            selected_profile=profile_dropdown.value,
        )
        page.update()

    def handle_platform_brightness_change(_e):
        if page.theme_mode == ft.ThemeMode.SYSTEM:
            apply_log_theme()
            if render_sidebar_fn[0]:
                render_sidebar_fn[0]()
            refresh_preview()
            page.update()

    theme_btn = ft.IconButton(
        icon=ft.Icons.LIGHT_MODE_OUTLINED,
        tooltip="Switch to Light Mode",
        on_click=toggle_theme,
    )
    update_theme_button()

    def toggle_window_maximize(_e=None):
        """Toggle the window between maximized and its previous size."""
        page.window.maximized = not page.window.maximized
        fullscreen_btn.icon = (
            ft.Icons.FULLSCREEN_EXIT if page.window.maximized else ft.Icons.FULLSCREEN
        )
        fullscreen_btn.tooltip = (
            "Restore window size" if page.window.maximized else "Maximize the window"
        )
        page.update()

    fullscreen_btn = ft.IconButton(
        icon=ft.Icons.FULLSCREEN,
        tooltip="Maximize the window",
        on_click=toggle_window_maximize,
    )

    open_output_btn = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN_OUTLINED,
        tooltip="Open Output Folder",
        on_click=lambda e: open_in_system(output_dir_val[0]),
    )

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
                ft.Row(
                    [
                        ft.Text("Documents", weight=ft.FontWeight.BOLD, size=16),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
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
        "Coding": get_font_families(project_fonts=CODING_FONT_CHOICES),
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
    code_font_dd = ft.Dropdown(
        label="Coding / Monospace Font",
        value="JetBrains Mono",
        options=[ft.dropdown.Option(f) for f in font_families["Coding"]],
        expand=True,
    )

    font_dropdowns = {
        "Bengali": bengali_font_dd,
        "Arabic": arabic_font_dd,
        "English": english_font_dd,
        "Headings": heading_font_dd,
        "Coding": code_font_dd,
    }

    def handle_font_select(e):
        dropdown = e.control
        if e.data is not None:
            dropdown.value = e.data

    for font_dropdown in font_dropdowns.values():
        font_dropdown.editable = True
        font_dropdown.enable_filter = True
        font_dropdown.enable_search = True
        font_dropdown.leading_icon = ft.Icons.SEARCH
        font_dropdown.hint_text = "Type to search fonts"
        font_dropdown.dense = True
        font_dropdown.menu_height = 280
        # Let Flet own editable-dropdown search state. Mutating ``value`` while
        # the user types rebuilds the menu and can move its scroll position.
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
                                ft.Text("Multilingual & Coding Fonts", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row([bengali_font_dd, arabic_font_dd], spacing=16),
                                ft.Row([english_font_dd, heading_font_dd], spacing=16),
                                ft.Row([code_font_dd], spacing=16),
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
            "code_font": code_font_dd.value,
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
            page.theme_mode = resolve_theme_mode(settings["theme_mode"])
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
    editor_saved_content = [""]
    editor_undo_stack = []
    editor_redo_stack = []
    editor_history_current = [{"text": "", "start": 0, "end": 0}]
    editor_history_limit = 200
    editor_undo_button = [None]
    editor_redo_button = [None]
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

    def capture_editor_snapshot():
        value = editor_field.value or ""
        selection = editor_field.selection
        if selection is not None:
            start, end = selection.start, selection.end
        elif last_editor_selection[0] is not None:
            start, end = last_editor_selection[0]
        else:
            start = end = 0
        return {"text": value, "start": start, "end": end}

    def refresh_history_buttons():
        if editor_undo_button[0] is not None:
            editor_undo_button[0].disabled = not editor_undo_stack
        if editor_redo_button[0] is not None:
            editor_redo_button[0].disabled = not editor_redo_stack

    def push_editor_undo_snapshot(previous_snapshot):
        editor_undo_stack.append(previous_snapshot.copy())
        if len(editor_undo_stack) > editor_history_limit:
            del editor_undo_stack[0]
        editor_redo_stack.clear()
        refresh_history_buttons()

    def record_editor_change(previous_snapshot):
        current = editor_field.value or ""
        if previous_snapshot["text"] == current:
            return False
        push_editor_undo_snapshot(previous_snapshot)
        editor_history_current[0] = capture_editor_snapshot()
        return True

    def reset_editor_history():
        editor_undo_stack.clear()
        editor_redo_stack.clear()
        editor_history_current[0] = capture_editor_snapshot()
        last_editor_selection[0] = (
            editor_history_current[0]["start"], editor_history_current[0]["end"]
        )
        refresh_history_buttons()

    def restore_editor_snapshot(snapshot):
        editor_field.value = snapshot["text"]
        editor_field.selection = ft.TextSelection(snapshot["start"], snapshot["end"])
        last_editor_selection[0] = (snapshot["start"], snapshot["end"])
        editor_history_current[0] = snapshot.copy()
        editor_dirty[0] = (editor_field.value or "") != editor_saved_content[0]
        refresh_editor_status()
        refresh_history_buttons()
        refresh_preview()
        page.run_task(editor_field.focus)
        page.update()

    def undo_editor_change(_e=None):
        if not editor_undo_stack:
            return
        editor_redo_stack.append(capture_editor_snapshot())
        restore_editor_snapshot(editor_undo_stack.pop())

    def redo_editor_change(_e=None):
        if not editor_redo_stack:
            return
        editor_undo_stack.append(capture_editor_snapshot())
        restore_editor_snapshot(editor_redo_stack.pop())

    def handle_editor_change(_e):
        previous_snapshot = editor_history_current[0].copy()
        current_value = editor_field.value or ""
        if editor_mode_dd.value != "Plain Text":
            selection = editor_field.selection
            if selection and selection.start == selection.end:
                caret = selection.start
            elif previous_snapshot["start"] == previous_snapshot["end"]:
                caret = previous_snapshot["start"] + 1
            else:
                caret = -1
            continuation = continue_markdown_block(
                previous_snapshot["text"], current_value, caret
            )
            if continuation is not None:
                current_value, caret = continuation
                editor_field.value = current_value
                editor_field.selection = ft.TextSelection(caret, caret)
                last_editor_selection[0] = (caret, caret)
        record_editor_change(previous_snapshot)
        editor_dirty[0] = (editor_field.value or "") != editor_saved_content[0]
        refresh_editor_status()
        refresh_preview()
        page.update()

    def handle_selection_change(e):
        try:
            last_editor_selection[0] = (e.selection.start, e.selection.end)
            if editor_history_current[0]["text"] == (editor_field.value or ""):
                editor_history_current[0]["start"] = e.selection.start
                editor_history_current[0]["end"] = e.selection.end
        except AttributeError:
            last_editor_selection[0] = None

    def handle_editor_mode_change(_e):
        plain = editor_mode_dd.value == "Plain Text"
        for button in format_buttons:
            button.disabled = plain
        refresh_editor_status()
        refresh_preview()
        page.update()

    async def restore_editor_focus_and_selection(expected_text, start, end):
        # Keyboard shortcuts arrive through the page-level key handler. Wait a
        # frame so the TextField can finish its native key handling before
        # restoring the formatting action's intended selection.
        await asyncio.sleep(0.05)
        if (editor_field.value or "") != expected_text:
            return
        await editor_field.focus()
        editor_field.selection = ft.TextSelection(start, end)
        last_editor_selection[0] = (start, end)
        if editor_history_current[0]["text"] == expected_text:
            editor_history_current[0]["start"] = start
            editor_history_current[0]["end"] = end
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
        previous_snapshot = editor_history_current[0].copy()
        editor_field.value = new_value
        editor_field.selection = ft.TextSelection(new_start, new_end)
        last_editor_selection[0] = (new_start, new_end)
        if new_value != value:
            push_editor_undo_snapshot(previous_snapshot)
        editor_history_current[0] = {
            "text": new_value, "start": new_start, "end": new_end
        }
        editor_dirty[0] = new_value != editor_saved_content[0]
        refresh_editor_status()
        refresh_history_buttons()
        refresh_preview()
        page.update()
        page.run_task(restore_editor_focus_and_selection, new_value, new_start, new_end)

    def format_button(icon, tooltip, producer):
        shortcut = {
            "Bold": "Ctrl+B",
            "Italic": "Ctrl+I",
            "Strikethrough": "Ctrl+Shift+X",
            "Heading level 1": "Ctrl+Alt+1",
            "Heading level 2": "Ctrl+Alt+2",
            "Heading level 3": "Ctrl+Alt+3",
            "Heading level 4": "Ctrl+Alt+4",
            "Heading level 5": "Ctrl+Alt+5",
            "Heading level 6": "Ctrl+Alt+6",
            "Bulleted list": "Ctrl+Shift+8",
            "Numbered list": "Ctrl+Shift+7",
            "Task list": "Ctrl+Shift+T",
            "Block quote": "Ctrl+Shift+Q",
            "Code block": "Ctrl+Shift+C",
            "Insert link": "Ctrl+K",
        }.get(tooltip)
        button = ft.IconButton(
            icon=icon,
            tooltip=f"{tooltip} ({shortcut})" if shortcut else tooltip,
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
        editor_saved_content[0] = editor_field.value or ""
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
        editor_field.selection = ft.TextSelection(0, 0)
        editor_file_path[0] = path
        editor_dirty[0] = False
        editor_saved_content[0] = content
        reset_editor_history()
        editor_mode_dd.value = (
            "Plain Text" if Path(path).suffix.lower() == ".txt" else "Markdown"
        )
        handle_editor_mode_change(None)
        append_log(f"[EDITOR] Opened '{Path(path).name}' in the editor.")
        page.run_task(editor_field.focus)
        page.update()

    def handle_editor_shortcut(e):
        """Route common file and Markdown shortcuts while the editor is active."""
        if active_view[0] != "editor" or not (e.ctrl or e.meta):
            return
        key = (e.key or "").lower()
        if key.startswith("key"):
            key = key[3:]
        if key == "s":
            page.run_task(handle_save_as if e.shift else handle_save_click, None)
        elif key == "o" and not e.shift:
            page.run_task(handle_open_in_editor, None)
        elif key == "z" and not e.shift:
            undo_editor_change()
        elif key == "y" or (key == "z" and e.shift):
            redo_editor_change()
        elif key == "b" and not e.shift:
            apply_transform(bold_producer())
        elif key == "i" and not e.shift:
            apply_transform(italic_producer())
        elif key == "k" and not e.shift:
            apply_transform(link_producer())
        elif key == "x" and e.shift:
            apply_transform(strikethrough_producer())
        elif key == "c" and e.shift:
            apply_transform(code_block_producer())
        elif key in {"`", "backquote"}:
            apply_transform(inline_code_producer())
        elif key == "t" and e.shift:
            apply_transform(task_list_producer())
        elif key == "q" and e.shift:
            apply_transform(quote_producer())
        elif key in {"7", "&"} and e.shift:
            apply_transform(ordered_list_producer())
        elif key in {"8", "*"} and e.shift:
            apply_transform(bullet_producer())
        elif key == "enter" and not e.shift:
            page.run_task(execute_editor_conversion, None)
        elif e.alt and key in {"1", "2", "3", "4", "5", "6"}:
            apply_transform(heading_producer(int(key)))

    page.on_keyboard_event = handle_editor_shortcut

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
        selection=ft.TextSelection(0, 0),
        hint_text="Paste or type Markdown or plain text here, then convert it directly to PDF.",
        text_style=ft.TextStyle(font_family="monospace"),
        text_size=14,
        # TextField expects a VerticalAlignment value here. A 2D Alignment
        # object can break the Flutter field and make the editor appear disabled.
        text_vertical_align=ft.VerticalAlignment.START,
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
        editor_field.selection = ft.TextSelection(0, 0)
        editor_file_path[0] = None
        editor_dirty[0] = False
        editor_saved_content[0] = ""
        reset_editor_history()
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


    editor_undo_button[0] = ft.IconButton(
        icon=ft.Icons.UNDO,
        tooltip="Undo last editor change",
        icon_size=18,
        width=32,
        height=32,
        style=ft.ButtonStyle(padding=0),
        disabled=True,
        on_click=undo_editor_change,
    )
    editor_redo_button[0] = ft.IconButton(
        icon=ft.Icons.REDO,
        tooltip="Redo editor change",
        icon_size=18,
        width=32,
        height=32,
        style=ft.ButtonStyle(padding=0),
        disabled=True,
        on_click=redo_editor_change,
    )
    editor_toolbar = ft.Row(
        [
            editor_undo_button[0],
            editor_redo_button[0],
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
            format_button(ft.Icons.LOOKS_4, "Heading level 4", heading_producer(4)),
            format_button(ft.Icons.LOOKS_5, "Heading level 5", heading_producer(5)),
            format_button(ft.Icons.LOOKS_6, "Heading level 6", heading_producer(6)),
            format_button(
                ft.Icons.FORMAT_LIST_BULLETED, "Bulleted list", bullet_producer()
            ),
            format_button(
                ft.Icons.FORMAT_LIST_NUMBERED, "Numbered list", ordered_list_producer()
            ),
            format_button(
                ft.Icons.CHECKLIST, "Task list", task_list_producer()
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
                            tooltip="Open document (Ctrl+O)",
                            on_click=handle_open_in_editor,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.SAVE,
                            tooltip="Save (Ctrl+S)",
                            on_click=handle_save_click,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.SAVE_AS,
                            tooltip="Save As... (Ctrl+Shift+S)",
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
    log_text = ft.Text(
        spans=[],
        size=12,
        font_family="monospace",
        selectable=True,
        expand=True,
    )
    log_column = ft.Column(
        [log_text], expand=True, scroll=ft.ScrollMode.AUTO, spacing=4, auto_scroll=True
    )

    async def copy_log(_e):
        if not log_messages:
            return
        try:
            await clipboard.set("\n".join(log_messages))
            for button in log_copy_buttons:
                button.icon = ft.Icons.CHECK
                button.tooltip = "Log copied"
            page.update()
        except Exception as error:
            append_log(f"[ERROR] Could not copy the conversion log: {error}")

    log_expanded = [False]

    def set_log_expanded(expanded):
        log_expanded[0] = expanded
        log_column.visible = expanded
        log_container.height = 160 if expanded else 48
        log_container.padding = 10 if expanded else ft.Padding(left=10, top=4, right=10, bottom=4)
        for button in log_toggle_buttons:
            button.icon = ft.Icons.KEYBOARD_ARROW_DOWN if expanded else ft.Icons.KEYBOARD_ARROW_UP
            button.tooltip = (
                "Collapse conversion log" if expanded else "Expand conversion log"
            )

    def toggle_log(_e=None):
        set_log_expanded(not log_expanded[0])
        page.update()

    log_header = ft.Row(
        [
            ft.Text("Conversion Log", weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            make_log_copy_button(),
            make_log_toggle_button(),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
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
        for button in log_copy_buttons:
            button.icon_color = "#444746" if light_mode else "#C4C7C5"
        for button in log_toggle_buttons:
            button.icon_color = "#444746" if light_mode else "#C4C7C5"
        refresh_log_text()

    page.on_platform_brightness_change = handle_platform_brightness_change

    def append_log(message):
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        log_messages.append(formatted_message)
        for button in log_copy_buttons:
            button.icon = ft.Icons.CONTENT_COPY
            button.tooltip = "Copy log"
        refresh_log_text()
        page.update()

    def refresh_log_text():
        """Render the log as one selectable text flow with per-line colors."""
        log_text.spans = [
            ft.TextSpan(
                text=f"[{time_text}] {message}\n",
                style=ft.TextStyle(color=log_entry_color(message)),
            )
            for time_text, message in (
                (line[1:9], line[11:]) if len(line) >= 11 else ("", line)
                for line in log_messages
            )
        ]

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
            update_primary_action()
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
        update_primary_action()
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
        if is_watching[0]:
            await toggle_watch_mode()
            return
        if active_view[0] == "editor":
            await execute_editor_conversion()
            return
        mode = list(mode_segmented.selected)[0] if mode_segmented.selected else "once"
        if mode == "auto":
            await toggle_watch_mode()
        else:
            await execute_conversion()

    def update_primary_action():
        """Keep the AppBar action aligned with the active view and watch state."""
        if active_view[0] == "editor":
            action_btn.visible = False
            action_btn.text = "Export PDF"
            action_btn.icon = ft.Icons.ROCKET_LAUNCH
            action_btn.tooltip = "Export the editor buffer to PDF"
        else:
            action_btn.visible = True
            if is_watching[0]:
                action_btn.text = "⏹ Stop Auto-Convert"
                action_btn.icon = ft.Icons.STOP
                action_btn.tooltip = "Stop the auto-convert watcher"
            else:
                action_btn.text = "Convert to PDF"
                action_btn.icon = ft.Icons.ROCKET_LAUNCH
                action_btn.tooltip = "Convert the selected documents to PDF"

    action_btn = ft.FilledButton(
        "Convert to PDF",
        icon=ft.Icons.ROCKET_LAUNCH,
        on_click=handle_action_click,
        style=ft.ButtonStyle(padding=14),
    )
    update_primary_action()

    # ---------------- Help Tab ----------------
    help_selected_topic = [None]
    help_topics_width = [260.0]
    help_topics_open = [True]
    HELP_TOPICS_MIN_WIDTH = 180
    HELP_TOPICS_MAX_WIDTH = 380
    def clear_help_search(_e=None):
        help_search_field.value = ""
        help_clear_btn.visible = False
        help_search_results.visible = False
        render_help_list(HELP_TOPICS)
        help_results_count.value = f"{len(HELP_TOPICS)} topics found"
        page.update()

    help_clear_btn = ft.TextButton(
        "Clear",
        icon=ft.Icons.CLEAR_ROUNDED,
        tooltip="Clear search",
        on_click=clear_help_search,
        visible=False,
    )

    def handle_search_focus(_e=None):
        if (help_search_field.value or "").strip():
            help_search_results.visible = True
            page.update()

    help_search_field = ft.TextField(
        label="Search help topics",
        hint_text="Type to filter topics, e.g. 'preview', 'fonts', 'toc'",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
        # Deferred so the handler can be defined after the control.
        on_change=lambda e: handle_help_search(e),
        on_focus=lambda e: handle_search_focus(e),
    )
    help_results_count = ft.Text("", size=12, color=ft.Colors.GREY_400)
    # Search results live under the search box so they stay reachable even
    # when the Topics pane is collapsed.
    help_search_results = ft.Column(spacing=2, visible=False, data="help-search-results")
    help_topic_list = ft.Column(spacing=2, expand=True, scroll=ft.ScrollMode.AUTO)
    help_topic_content = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)

    def render_help_list(matches, target=None):
        target = target or help_topic_list
        target.controls = [help_topic_card(topic) for topic in matches]

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
        query = (help_search_field.value or "").strip()
        help_clear_btn.visible = bool(query)
        help_search_results.visible = bool(query)
        matches = search_help_topics(help_search_field.value) if query else HELP_TOPICS
        help_results_count.value = (
            f"{len(matches)} topic{'s' if len(matches) != 1 else ''} found"
        )
        render_help_list(matches, help_search_results)
        render_help_list(matches)
        if query:
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
        selected = (
            help_topics_open[0]
            and topic["title"] == help_selected_topic[0]
        )
        is_light = is_light_theme()
        if selected:
            card_bgcolor = "#E8F0FE" if is_light else "#1E3A5F"
            card_border = ft.Border.all(1, "#1967D2" if is_light else "#8AB4F8")
            title_color = "#1967D2" if is_light else "#8AB4F8"
        else:
            card_bgcolor = None
            card_border = None
            title_color = None

        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(topic["title"], weight=ft.FontWeight.W_600, size=13, color=title_color),
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
                bgcolor=card_bgcolor,
                border=card_border,
                border_radius=8,
            ),
            margin=ft.Margin(bottom=4, left=0, right=0, top=0),
        )

    def _select_help_topic(topic):
        render_help_topic(topic)
        help_search_results.visible = False
        query = (help_search_field.value or "").strip()
        help_clear_btn.visible = bool(query)
        matches = search_help_topics(help_search_field.value) if query else HELP_TOPICS
        render_help_list(matches)
        page.update()

    # --- Help navigation buttons (defined first so float_row can reference float_btn) ---
    help_topics_toggle_btn = ft.IconButton(
        icon=ft.Icons.MENU_ROUNDED,
        icon_size=20,
        width=32,
        height=32,
        tooltip="Collapse the Topics pane",
        # on_click wired after toggle_help_topics is defined below.
    )
    help_topics_float_btn = ft.IconButton(
        icon=ft.Icons.MENU_ROUNDED,
        icon_size=20,
        width=32,
        height=32,
        tooltip="Show the Topics pane",
        # on_click wired after toggle_help_topics is defined below.
    )
    # Float row: shown above content when the Topics pane is hidden.
    help_topics_float_row = ft.Row(
        [help_topics_float_btn],
        visible=False,
        data="help-float-row",
    )

    def toggle_help_topics(_e=None):
        help_topics_open[0] = not help_topics_open[0]
        help_topics_pane.visible = help_topics_open[0]
        help_topics_divider.visible = help_topics_open[0]
        help_topics_toggle_btn.tooltip = (
            "Collapse the Topics pane" if help_topics_open[0] else "Show the Topics pane"
        )
        # Show the floating hamburger row above content when pane is collapsed.
        help_topics_float_row.visible = not help_topics_open[0]
        matches = search_help_topics(help_search_field.value)
        render_help_list(matches)
        page.update()

    # Wire on_click now that toggle_help_topics exists.
    help_topics_toggle_btn.on_click = toggle_help_topics
    help_topics_float_btn.on_click = toggle_help_topics

    def resize_help_split(e):
        delta = e.primary_delta or 0
        help_topics_width[0] = max(
            HELP_TOPICS_MIN_WIDTH,
            min(HELP_TOPICS_MAX_WIDTH, help_topics_width[0] + delta),
        )
        help_topics_pane.width = help_topics_width[0]
        page.update()

    help_topics_pane = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Topics", weight=ft.FontWeight.W_600, size=13),
                        ft.Container(expand=True),
                        help_topics_toggle_btn,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=4),
                help_topic_list,
            ],
            spacing=4,
            expand=True,
        ),
        width=help_topics_width[0],
        data="help-topics-pane",
    )
    help_topics_divider = ft.GestureDetector(
        content=ft.Container(
            content=ft.VerticalDivider(width=14, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
            width=14,
        ),
        drag_interval=1,
        on_horizontal_drag_update=resize_help_split,
        mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
        data="help-topics-divider",
    )

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
                                    [help_search_field, help_clear_btn, help_results_count],
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=8,
                                ),
                                help_search_results,
                            ],
                            spacing=10,
                        ),
                        padding=16,
                    )
                ),
                ft.Row(
                    [
                        help_topics_pane,
                        help_topics_divider,
                        ft.Container(
                            content=ft.Column(
                                [
                                    # Shown only when the topics pane is hidden;
                                    # sits above the content, not over it.
                                    help_topics_float_row,
                                    ft.Container(
                                        content=help_topic_content,
                                        expand=True,
                                        padding=ft.Padding(left=12, top=0, right=0, bottom=0),
                                    ),
                                ],
                                spacing=4,
                                expand=True,
                            ),
                            expand=True,
                            data="help-details",
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

    # ---------------- Assemble Sidebar & Views ----------------
    view_controls = {
        "editor": editor_tab,
        "documents": files_tab,
        "geometry": geometry_tab,
        "typography": typography_tab,
        "toc": toc_tab,
        "profiles": profiles_tab,
        "help": help_tab,
    }
    view_holder = ft.Container(expand=True, content=editor_tab, data="view-holder")

    SIDEBAR_EXPANDED_WIDTH = 216
    SIDEBAR_COLLAPSED_WIDTH = 64
    preference_view_keys = {"geometry", "typography", "toc", "profiles"}

    nav_items = [
        ("editor", "Editor", ft.Icons.EDIT_OUTLINED, False),
        ("documents", "Documents", ft.Icons.DESCRIPTION_OUTLINED, False),
        ("preferences", "Preferences", ft.Icons.TUNE, False),
        ("geometry", "Page and Geometry", ft.Icons.ASPECT_RATIO, True),
        ("typography", "Typography", ft.Icons.FONT_DOWNLOAD_OUTLINED, True),
        ("toc", "TOC & Page Numbers", ft.Icons.FORMAT_LIST_NUMBERED, True),
        ("profiles", "Profiles", ft.Icons.BOOKMARKS_OUTLINED, True),
        ("help", "Help", ft.Icons.HELP_OUTLINE, False),
    ]

    sidebar_column = ft.Column(spacing=4, expand=True, scroll=ft.ScrollMode.AUTO)
    sidebar_container = ft.Container(
        content=sidebar_column,
        width=SIDEBAR_EXPANDED_WIDTH,
        padding=ft.Padding(left=4, top=4, right=4, bottom=4),
    )

    def _nav_item_selected(key):
        if key == "preferences":
            return active_view[0] in preference_view_keys
        return active_view[0] == key

    def handle_nav_click(key):
        if key == "preferences":
            if not sidebar_expanded[0]:
                sidebar_expanded[0] = True
                preferences_expanded[0] = True
            elif not preferences_expanded[0]:
                preferences_expanded[0] = True
                if active_view[0] not in preference_view_keys:
                    show_view("geometry")
                    return
            elif active_view[0] in preference_view_keys:
                preferences_expanded[0] = False
            else:
                show_view("geometry")
                return
        else:
            show_view(key)
            return
        render_sidebar()
        page.update()

    def render_sidebar():
        """Rebuild the shrinkable sidebar for the current expansion state."""
        expanded = sidebar_expanded[0]
        sidebar_container.width = (
            SIDEBAR_EXPANDED_WIDTH if expanded else SIDEBAR_COLLAPSED_WIDTH
        )
        is_light = is_light_theme()
        controls = [
            ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.MENU_ROUNDED,
                        icon_size=22,
                        width=38,
                        height=38,
                        tooltip="Collapse sidebar" if expanded else "Expand sidebar",
                        on_click=lambda _e: toggle_sidebar(),
                    )
                ],
                alignment=ft.MainAxisAlignment.START if expanded else ft.MainAxisAlignment.CENTER,
            )
        ]
        for key, label, icon, is_child in nav_items:
            if is_child and (not expanded or not preferences_expanded[0]):
                continue
            if is_child and key not in preference_view_keys:
                continue
            selected = _nav_item_selected(key)
            if selected:
                item_bgcolor = "#E8F0FE" if is_light else "#1E3A5F"
                item_color = "#1967D2" if is_light else "#8AB4F8"
                item_weight = ft.FontWeight.W_600
            else:
                item_bgcolor = None
                item_color = "#444746" if is_light else "#C4C7C5"
                item_weight = ft.FontWeight.W_500

            if expanded:
                row = ft.Row(
                    [
                        ft.Icon(icon, size=18, color=item_color),
                        ft.Text(label, size=13, weight=item_weight, color=item_color),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
                if is_child:
                    row = ft.Row([ft.Container(width=10), row], spacing=0)
            else:
                row = ft.Row(
                    [ft.Icon(icon, size=18, color=item_color)],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            controls.append(
                ft.Container(
                    content=row,
                    padding=ft.Padding(left=10, top=8, right=10, bottom=8),
                    border_radius=8,
                    bgcolor=item_bgcolor,
                    ink=True,
                    tooltip=label,
                    data=key,
                    on_click=lambda _e, k=key: handle_nav_click(k),
                )
            )
        sidebar_column.controls = controls

    def toggle_sidebar(_e=None):
        sidebar_expanded[0] = not sidebar_expanded[0]
        render_sidebar()
        page.update()

    def show_view(key):
        """Switch the single content pane and scope the conversion log."""
        if key not in view_controls:
            return
        active_view[0] = key
        view_holder.content = view_controls[key]
        # The conversion log belongs only to Editor and Documents.
        log_container.visible = key in {"editor", "documents"}
        set_log_expanded(key != "editor")
        update_primary_action()
        render_sidebar()
        page.update()

    render_sidebar_fn[0] = render_sidebar
    render_sidebar()
    set_log_expanded(False)

    # AppBar conversion controls. Handlers are attached after every action
    # control exists, so the bar itself is assembled at the end of main().
    app_bar = ft.AppBar(
        leading=ft.Icon(ft.Icons.PICTURE_AS_PDF_ROUNDED, color=ft.Colors.AMBER_400),
        title=ft.Text("PDF Creator Studio", weight=ft.FontWeight.BOLD),
        center_title=False,
        actions=[
            action_btn,
            open_pdf_btn,
            open_output_btn,
            mode_segmented,
            ft.Container(width=16),
            fullscreen_btn,
            theme_btn,
        ],
    )
    page.appbar = app_bar

    # Main view structure
    page.add(
        ft.Row(
            [
                sidebar_container,
                ft.VerticalDivider(width=1, thickness=1),
                view_holder,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        ft.Divider(height=4),
        ft.Row(
            [
                status_badge,
                ft.Container(expand=True),
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
