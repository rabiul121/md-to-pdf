import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import converter


class ConverterOptionsTests(unittest.TestCase):
    def test_custom_output_and_language_options_are_passed_to_pandoc(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.txt"
            output_directory = root / "custom-output"
            source.write_text("A plain text document", encoding="utf-8")

            with patch.object(converter, "find_executable", side_effect=["pandoc", "xelatex"]), patch.object(
                converter,
                "font_file_supports_codepoint",
                side_effect=lambda _selection, codepoint: codepoint == 0x0041,
            ), patch.object(
                converter.subprocess,
                "run",
                return_value=converter.subprocess.CompletedProcess([], 0, "", ""),
            ) as run:
                success, output_path = converter.convert_md_to_pdf(
                    source,
                    output_name="custom-name.pdf",
                    output_directory=output_directory,
                    toc_language="Bangla",
                    page_number_language="Bangla",
                    page_border=True,
                    front_page_numbers=True,
                    front_page_number_style="roman",
                    front_page_number_format="Page 1 of 10",
                    front_page_number_position="Bottom right",
                    front_page_number_size="11pt",
                    front_page_number_language="Bangla",
                    page_size_choice="For Mobile",
                    font_size_choice="Standard",
                    toc_alignment="Right",
                    toc_design="Decorative",
                    heading_font="Inter",
                    hyphenation=False,
                    line_height="1.25",
                    paragraph_spacing="9pt",
                    log_func=lambda _message: None,
                )

            self.assertTrue(success)
            self.assertNotIn("copyfriendlytext=true", run.call_args.args[0])
            self.assertEqual(Path(output_path), output_directory / "custom-name.pdf")
            command = run.call_args.args[0]
            self.assertIn("--from=markdown", command)
            self.assertIn("-V", command)
            self.assertIn("toclanguagebangla=true", command)
            self.assertIn("pagenumberlanguagebangla=true", command)
            self.assertIn("frontpagenumbers=true", command)
            self.assertIn("frontpagenumberstyle=roman", command)
            self.assertIn("frontpagenumberposition=R", command)
            self.assertIn("frontpagenumbersize=11pt", command)
            self.assertIn("frontpagenumberlanguagebangla=true", command)
            front_bangla_text = next(argument for argument in command if argument.startswith("frontpagenumbertextbangla="))
            self.assertIn("পৃষ্ঠা", front_bangla_text)
            self.assertIn("fontenglishfile=DejaVuSans.ttf", command)
            self.assertIn("fontbengalifile=SolaimanLipi.ttf", command)
            self.assertIn("fontarabicfile=Amiri-Regular.ttf", command)
            self.assertIn("fontheadinglatinfile=Inter-VariableFont_opsz,wght.ttf", command)
            self.assertIn("fontheadingbengalifile=SolaimanLipi.ttf", command)
            self.assertTrue(any(argument.startswith("fontenglishpath=") and argument.endswith("/assets/fonts/english/") for argument in command))
            self.assertIn("lineheight=1.25", command)
            self.assertIn("paragraphspacing=9pt", command)
            self.assertNotIn("hyphenation=true", command)
            bangla_footer = next(argument for argument in command if argument.startswith("pagenumbertextbangla="))
            self.assertLess(bangla_footer.index(r"\getpagerefnumber{LastPage}"), bangla_footer.index(r"\arabic{page}"))
            self.assertIn(r"\bangladigits{\getpagerefnumber{LastPage}}", bangla_footer)
            self.assertNotIn(r"\pageref*{LastPage}", bangla_footer)
            self.assertIn("pageborder=true", command)
            self.assertIn(r"toctitlealignment=\hfill", command)
            self.assertIn("toctitleendfill=", command)
            self.assertIn("toctitlesize=16pt", command)
            self.assertIn("toctitlecolor=teal!65!black", command)
            self.assertIn("tocentrycolor=teal!55!black", command)
            self.assertIn(r"tocaftertitle=\par\medskip\hrule height 1pt\bigskip", command)

    def test_existing_output_files_are_preserved_with_incrementing_suffix(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.md"
            output_directory = root / "output"
            output_directory.mkdir()
            source.write_text("A plain text document", encoding="utf-8")
            existing_output = output_directory / "result.pdf"
            existing_first_suffix = output_directory / "result_1.pdf"
            existing_output.write_bytes(b"original PDF")
            existing_first_suffix.write_bytes(b"first suffixed PDF")

            with patch.object(converter, "find_executable", side_effect=["pandoc", "xelatex"]), patch.object(
                converter.subprocess,
                "run",
                return_value=converter.subprocess.CompletedProcess([], 0, "", ""),
            ) as run:
                success, output_path = converter.convert_md_to_pdf(
                    source,
                    output_name="result.pdf",
                    output_directory=output_directory,
                    log_func=lambda _message: None,
                )

            self.assertTrue(success)
            self.assertEqual(Path(output_path), output_directory / "result_2.pdf")
            self.assertIn(str(output_directory / "result_2.pdf"), run.call_args.args[0])
            self.assertEqual(existing_output.read_bytes(), b"original PDF")
            self.assertEqual(existing_first_suffix.read_bytes(), b"first suffixed PDF")

    def test_copy_friendly_text_can_be_enabled_without_changing_default(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.md"
            source.write_text("বাংলা text", encoding="utf-8")
            with patch.object(converter, "find_executable", side_effect=["pandoc", "xelatex"]), patch.object(
                converter.subprocess,
                "run",
                return_value=converter.subprocess.CompletedProcess([], 0, "", ""),
            ) as run:
                success, _result = converter.convert_md_to_pdf(
                    source,
                    copy_friendly_text=True,
                    log_func=lambda _message: None,
                )

        self.assertTrue(success)
        self.assertIn("copyfriendlytext=true", run.call_args.args[0])

    def test_system_fonts_follow_project_fonts_in_alphabetical_order(self):
        with patch("tkinter.font.families", return_value=("Zeta Font", "DejaVu Sans", "Arial", "Beta Font")):
            fonts = converter.get_font_families(None, ["Project Font", "DejaVu Sans"])

        self.assertEqual(fonts, ["Project Font", "DejaVu Sans", "Arial", "Beta Font", "Zeta Font"])

    def test_font_search_filters_case_insensitively(self):
        families = ["BenSenHandwriting", "Noto Serif", "BenSen", "Arial"]
        self.assertEqual(converter.filter_font_families("bEn", families), ["BenSenHandwriting", "BenSen"])
        self.assertEqual(converter.filter_font_families("", families), families)
        self.assertEqual(converter.filter_font_families("Search fonts", families), families)

    def test_heading_font_uses_script_coverage_fallbacks(self):
        def resolve(family, _role):
            return {
                "BenSenHandwriting": ("BenSen.ttf", "/fonts/bensen/"),
                "Arial": ("Arial.ttf", "/fonts/latin/"),
                "Nirmala UI": ("Nirmala.ttf", "/fonts/bengali/"),
                "Amiri": ("Amiri.ttf", "/fonts/arabic/"),
            }.get(family)

        def coverage(font_selection, codepoint):
            font_file = font_selection[0]
            return (font_file == "BenSen.ttf" and codepoint == 0x0985) or (font_file == "Arial.ttf" and codepoint == 0x0041)

        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "heading.md"
            source.write_text("# বাংলা heading", encoding="utf-8")
            with patch.object(converter, "find_executable", side_effect=["pandoc", "xelatex"]), patch.object(
                converter, "resolve_font_file", side_effect=resolve
            ), patch.object(converter, "font_file_supports_codepoint", side_effect=coverage), patch.object(
                converter.subprocess,
                "run",
                return_value=converter.subprocess.CompletedProcess([], 0, "", ""),
            ) as run:
                success, _result = converter.convert_md_to_pdf(
                    source,
                    english_font="Arial",
                    heading_font="BenSenHandwriting",
                    bengali_font="Nirmala UI",
                    arabic_font="Amiri",
                    log_func=lambda _message: None,
                )

        self.assertTrue(success)
        command = run.call_args.args[0]
        self.assertIn("fontheadingbengalifile=BenSen.ttf", command)
        self.assertIn("fontheadinglatinfile=Arial.ttf", command)

    def test_builtin_profiles_merge_with_and_preserve_saved_profiles(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_path = Path(temporary_directory) / "profiles.json"
            profile_path.write_text('{"My Profile": {"line_height": "1.4", "hyphenation": false}}', encoding="utf-8")
            with patch.object(converter, "PROFILE_PATH", profile_path):
                profiles = converter.load_profiles()
                converter.save_profile("My Profile", {**profiles["My Profile"], "heading_font": "Inter"})
                converter.save_last_used_settings({"line_height": "1.5", "heading_font": "Noto Serif"})
                saved = converter.load_profiles()

        self.assertTrue({"Mobile", "PC", "English", "Bangla", "Minimal", "Decorative"}.issubset(saved))
        self.assertEqual(saved["My Profile"]["line_height"], "1.4")
        self.assertFalse(saved["My Profile"]["hyphenation"])
        self.assertEqual(saved["My Profile"]["heading_font"], "Inter")
        self.assertEqual(saved[converter.LAST_USED_PROFILE]["line_height"], "1.5")
        self.assertEqual(saved[converter.LAST_USED_PROFILE]["heading_font"], "Noto Serif")

    def test_builtin_profile_cannot_be_overwritten_or_deleted(self):
        with self.assertRaises(ValueError):
            converter.save_profile("Mobile", {"page_size_choice": "A4"})
        with self.assertRaises(ValueError):
            converter.delete_profile("Bangla")

    def test_bangla_toc_page_digits_do_not_depend_on_footer_language(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.md"
            source.write_text("# Heading", encoding="utf-8")
            with patch.object(converter, "find_executable", side_effect=["pandoc", "xelatex"]), patch.object(
                converter.subprocess,
                "run",
                return_value=converter.subprocess.CompletedProcess([], 0, "", ""),
            ) as run:
                success, _result = converter.convert_md_to_pdf(
                    source,
                    toc_language="Bangla",
                    page_number_language="English",
                    log_func=lambda _message: None,
                )

        self.assertTrue(success)
        command = run.call_args.args[0]
        self.assertIn("toclanguagebangla=true", command)
        self.assertIn("tocpagebangla=true", command)
        self.assertNotIn("pagenumberlanguagebangla=true", command)

    def test_template_uses_full_digit_conversion_indentfirst_and_bold_heading_face(self):
        template = converter.TEMPLATE_PATH.read_text(encoding="utf-8")
        gui_source = (converter.APP_DIR / "converter.py").read_text(encoding="utf-8")

        self.assertIn(r"\makebox[\@pnumwidth][\cftpnumalign]{\cftsecpagefont\tocpagevalue{#1}}", template)
        self.assertNotIn(r"\pagenumbering{gobble}", template)
        self.assertIn(r"\fancyfoot{}", template)
        self.assertIn(r"\newcommand{\setfrontpagenumbers}", template)
        self.assertIn(r"\XeTeXgenerateactualtext=1", template)
        self.assertIn(r"\newcommand{\setmainpagenumbers}", template)
        self.assertLess(template.index(r"\setfrontpagenumbers"), template.index(r"\tableofcontents"))
        self.assertLess(template.index(r"\clearpage", template.index(r"\tableofcontents")), template.index(r"\setmainpagenumbers", template.index(r"\tableofcontents")))
        self.assertIn(r"\usepackage{indentfirst}", template)
        self.assertIn(r"\headinglatinfont", template)
        self.assertIn(r"\headingbengalifont #1", template)
        self.assertIn(r"\newenvironment{ArabicParagraph}{\begin{RTL}\raggedleft\setlength{\parindent}{0pt}}", template)
        self.assertIn(r"\setlength{\cftsecindent}{0pt}", template)
        self.assertIn(r"\setlength{\cftsecnumwidth}{0pt}", template)
        self.assertIn(r"\setlength{\cftsubsecindent}{0pt}", template)
        self.assertIn(r"\setlength{\cftsubsecnumwidth}{0pt}", template)
        self.assertIn(r"\cftsetpnumwidth{2.2em}", template)
        self.assertIn(r"\cftsetrmarg{3.2em}", template)
        self.assertIn(r"\renewcommand{\cftsecdotsep}{\cftdotsep}", template)
        lua_filter = (converter.APP_DIR / "font_filter.lua").read_text(encoding="utf-8")
        self.assertIn('traverse = "topdown"', lua_filter)
        self.assertIn("function Header(el)", lua_filter)
        self.assertIn('pandoc.utils.stringify(el):match("^%s*$")', lua_filter)
        self.assertIn(r'pandoc.RawInline("latex", "\\noindent")', lua_filter)
        self.assertIn("FakeBold=2", template)
        self.assertIn("font_picker = ttk.Combobox(typography_tab", gui_source)
        self.assertNotIn("search_entry = ttk.Entry(typography_tab", gui_source)

    def test_windows_uses_system_symbol_and_currency_fonts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "symbols.md"
            source.write_text("♞ ⚑ ⚐ ➜ ₹ 🫱🫲 🖟 🖺", encoding="utf-8")

            with patch.object(converter, "find_executable", side_effect=["pandoc", "xelatex"]), patch.object(
                converter.subprocess,
                "run",
                return_value=converter.subprocess.CompletedProcess([], 0, "", ""),
            ) as run:
                success, _result = converter.convert_md_to_pdf(
                    source,
                    log_func=lambda _message: None,
                )

        self.assertTrue(success)
        command = run.call_args.args[0]
        self.assertIn("fontemoji=Segoe UI Emoji", command)
        self.assertIn("fontsymbol=Segoe UI Symbol", command)
        emoji_font_path = converter.BASE_DIR / "assets" / "fonts" / "symbol" / "seguiemj.ttf"
        symbol_font_path = converter.BASE_DIR / "assets" / "fonts" / "symbol" / "seguisym.ttf"
        if emoji_font_path.is_file():
            self.assertIn("fontemojifile=seguiemj.ttf", command)
            self.assertTrue(any(argument.startswith("fontemojipath=") and argument.endswith("/assets/fonts/symbol/") for argument in command))
        else:
            self.assertNotIn("fontemojifile=seguiemj.ttf", command)
        if symbol_font_path.is_file():
            self.assertIn("fontsymbolfile=seguisym.ttf", command)
        else:
            self.assertNotIn("fontsymbolfile=seguisym.ttf", command)
        self.assertIn("fontcurrency=Segoe UI", command)
        self.assertIn("fontemojiSupplementfile=NotoEmoji-VariableFont_wght.ttf", command)

        template = converter.TEMPLATE_PATH.read_text(encoding="utf-8")
        lua_filter = converter.LUA_FILTER_PATH.read_text(encoding="utf-8")
        self.assertIn(r"\newfontfamily\currencyfont{$fontcurrency$}", template)
        self.assertIn(r"\newcommand{\currency}[1]{{\currencyfont #1}}", template)
        self.assertIn(r'output = output .. "\\currency{" .. escape_latex(char) .. "}"', lua_filter)
        self.assertIn(r'output = output .. "\\symb{" .. escape_latex(char) .. "}"', lua_filter)
        self.assertIn(r'output = output .. "\\emojisupplement{" .. escape_latex(char) .. "}"', lua_filter)
        self.assertIn("or code == 0x1F59F or code == 0x1F5BA", lua_filter)
        self.assertIn("if is_symbol_only_char(current)", lua_filter)

    def test_template_sets_title_before_maketitle(self):
        template = converter.TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(r"\title{", template)
        self.assertIn(r"\maketitle", template)
        self.assertLess(template.index(r"\title{"), template.index(r"\maketitle"))

    def test_post_conversion_menu_returns_expected_action(self):
        with patch("builtins.input", side_effect=["2"]), patch.object(converter, "open_in_system") as open_in_system:
            action = converter.prompt_post_conversion_menu(["/tmp/result.pdf"], "/tmp/output")

        self.assertEqual(action, "open-output")
        open_in_system.assert_called_once_with(str(Path("/tmp/output")))

    def test_windows_emoji_ranges_are_supported_in_lua_filter(self):
        filter_source = (converter.APP_DIR / "font_filter.lua").read_text(encoding="utf-8")
        self.assertIn("0x1F1E6", filter_source)
        self.assertIn("0x1F000", filter_source)
        self.assertIn("0x2300", filter_source)
        self.assertIn("0x2500", filter_source)
        self.assertIn("0x2200", filter_source)
        self.assertIn("0x200D", filter_source)
        self.assertIn("0x20E3", filter_source)

    def test_font_coverage_parser_ignores_malformed_ranges(self):
        with patch("src.converter.shutil.which", return_value="fc-query"), patch("pathlib.Path.is_file", return_value=True), patch.object(
            converter.subprocess,
            "run",
            return_value=converter.subprocess.CompletedProcess([], 0, "1df1e20-7e\n", ""),
        ):
            self.assertFalse(converter.font_file_supports_codepoint(("TestFont.ttf", "."), 0x0985))

    def test_batch_uses_each_source_stem(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            sources = [root / "first.md", root / "second.md"]
            for source in sources:
                source.write_text("# Heading", encoding="utf-8")

            with patch.object(converter, "find_executable", side_effect=["pandoc", "xelatex"] * 2), patch.object(
                converter.subprocess,
                "run",
                return_value=converter.subprocess.CompletedProcess([], 0, "", ""),
            ):
                results = converter.convert_many_to_pdf(sources, output_directory=root / "pdfs", log_func=lambda _message: None)

            self.assertEqual([success for _source, success, _result in results], [True, True])
            self.assertEqual([Path(result).name for _source, _success, result in results], ["first.pdf", "second.pdf"])


if __name__ == "__main__":
    unittest.main()
