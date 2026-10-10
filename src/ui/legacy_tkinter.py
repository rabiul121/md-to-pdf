"""Legacy Tkinter interface for md-to-pdf."""

import os
import sys
import time
import threading
from pathlib import Path

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
    save_profile,
    save_last_used_settings,
    delete_profile,
)
from src.core.engine import (
    convert_md_to_pdf,
    convert_many_to_pdf,
    open_in_system,
    get_font_families,
    filter_font_families,
)
from src.cli.wizard import cli_interactive_flow

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
    root.title("PDF Creator Studio")
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
    ttk.Label(title_row, text="📄 PDF Creator Studio", style="Header.TLabel").pack(side=tk.LEFT, anchor="w")
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
        bundled_fonts = HEADING_FONT_CHOICES if label == "Headings" else PROJECT_FONT_CHOICES.get(label, PROJECT_FONT_CHOICES["English"])
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
