"""
Interactive command-line wizard for md-to-pdf.
"""

import time
from pathlib import Path

from src.core.constants import (
    INPUT_DIR,
    OUTPUT_DIR,
    SUPPORTED_INPUT_EXTENSIONS,
    MARGIN_PRESETS,
)
from src.core.engine import (
    convert_md_to_pdf,
    convert_many_to_pdf,
    open_in_system,
)


def ask_yes_no(prompt, default):
    """Prompt user for a yes/no response with a default value."""
    answer = input(f"{prompt} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not answer else answer in ("y", "yes")


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


def cli_interactive_flow(auto_mode=False):
    """Interactive command-line flow with user prompts."""
    while True:
        print("=" * 55)
        print(" Multilingual Markdown to PDF Converter")
        print(" Support: Bengali (SolaimanLipi), Arabic (Amiri), Symbols")
        print("=" * 55)

        # 1. Select Input File
        md_files = (
            sorted(
                path
                for path in INPUT_DIR.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS
            )
            if INPUT_DIR.exists()
            else []
        )
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
                    paths = [
                        part.strip().strip('"')
                        for part in input("Enter supported file path(s), separated by semicolons: ").split(";")
                        if part.strip()
                    ]
                    if paths and all(
                        Path(path).is_file() and Path(path).suffix.lower() in SUPPORTED_INPUT_EXTENSIONS
                        for path in paths
                    ):
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
                paths = [
                    part.strip().strip('"')
                    for part in input("Enter supported file path(s), separated by semicolons: ").split(";")
                    if part.strip()
                ]
                if paths and all(
                    Path(path).is_file() and Path(path).suffix.lower() in SUPPORTED_INPUT_EXTENSIONS
                    for path in paths
                ):
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
        margin_choice = (
            margin_names[int(margin_choice_input) - 1]
            if margin_choice_input.isdigit() and 1 <= int(margin_choice_input) <= len(margin_names)
            else "Page default"
        )
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
            conversion_options = dict(
                english_font=english_font,
                heading_font=heading_font,
                bengali_font=bengali_font,
                arabic_font=arabic_font,
                margin_choice=margin_choice,
                custom_margin=custom_margin,
                orientation=orientation,
                page_numbers=page_numbers,
                page_number_style=page_number_style,
                page_number_format=page_number_format,
                page_number_position=page_number_position,
                page_number_size=page_number_size,
                page_number_language=page_number_language,
                front_page_numbers=front_page_numbers,
                front_page_number_style=front_page_number_style,
                front_page_number_format=front_page_number_format,
                front_page_number_position=front_page_number_position,
                front_page_number_size=front_page_number_size,
                front_page_number_language=front_page_number_language,
                indent_first_line=indent_first_line,
                indent_amount=indent_amount,
                paragraph_spacing=paragraph_spacing,
                center_headings=center_headings,
                bold_headings=bold_headings,
                include_toc=include_toc,
                beautify_toc=beautify_toc,
                toc_language=toc_language,
                page_border=page_border,
                toc_alignment=toc_alignment,
                toc_design=toc_design,
                hyphenation=hyphenation,
                line_height=line_height,
                copy_friendly_text=copy_friendly_text,
                output_directory=output_directory,
                output_name=output_name,
            )
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
            results = convert_many_to_pdf(
                input_files,
                page_size_choice=selected_page_size,
                font_size_choice=selected_font_size,
                custom_font_size=custom_font_size,
                output_name=output_name,
                english_font=english_font,
                heading_font=heading_font,
                bengali_font=bengali_font,
                arabic_font=arabic_font,
                margin_choice=margin_choice,
                custom_margin=custom_margin,
                orientation=orientation,
                page_numbers=page_numbers,
                page_number_style=page_number_style,
                page_number_format=page_number_format,
                page_number_position=page_number_position,
                page_number_size=page_number_size,
                page_number_language=page_number_language,
                front_page_numbers=front_page_numbers,
                front_page_number_style=front_page_number_style,
                front_page_number_format=front_page_number_format,
                front_page_number_position=front_page_number_position,
                front_page_number_size=front_page_number_size,
                front_page_number_language=front_page_number_language,
                indent_first_line=indent_first_line,
                indent_amount=indent_amount,
                paragraph_spacing=paragraph_spacing,
                center_headings=center_headings,
                bold_headings=bold_headings,
                include_toc=include_toc,
                beautify_toc=beautify_toc,
                toc_language=toc_language,
                page_border=page_border,
                toc_alignment=toc_alignment,
                toc_design=toc_design,
                hyphenation=hyphenation,
                line_height=line_height,
                copy_friendly_text=copy_friendly_text,
                output_directory=output_directory,
            )
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
