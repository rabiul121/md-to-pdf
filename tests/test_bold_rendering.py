import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import converter
from src.core import engine


class BoldRenderingTests(unittest.TestCase):
    def test_regular_only_font_gets_synthetic_styles(self):
        selection = engine.resolve_bundled_font("DejaVu Sans", "english")
        features = engine.font_style_features(selection)
        self.assertIn("BoldFont={DejaVuSans-Regular.ttf}", features)
        self.assertIn("BoldFeatures={FakeBold=2}", features)
        self.assertIn("ItalicFeatures={FakeSlant=0.2}", features)
        self.assertIn("BoldItalicFeatures={FakeBold=2,FakeSlant=0.2}", features)

    def test_real_font_styles_are_preferred(self):
        selection = engine.resolve_bundled_font("Georgia", "english")
        features = engine.font_style_features(selection)
        self.assertIn("BoldFont={Georgia-Bold.ttf}", features)
        self.assertIn("ItalicFont={Georgia-Italic.ttf}", features)
        self.assertIn("BoldItalicFont={Georgia-BoldItalic.ttf}", features)
        self.assertNotIn("Fake", features)

    def test_variable_fonts_get_bold_fallback(self):
        selection = engine.resolve_bundled_font("Noto Sans", "english")
        self.assertIn("BoldFeatures={FakeBold=2}", engine.font_style_features(selection))

    def test_both_conversion_entry_points_pass_style_features(self):
        for module in (engine, converter):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "bold.md"
                source.write_text("Normal **bold**", encoding="utf-8")
                with patch.object(module, "find_executable", side_effect=["pandoc", "xelatex"]), patch.object(
                    module, "font_file_supports_codepoint", return_value=False
                ), patch.object(
                    module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")
                ) as run:
                    success, _ = module.convert_md_to_pdf(
                        source, output_directory=directory, bold_headings=False,
                        include_toc=False, log_func=lambda _message: None,
                    )
                self.assertTrue(success)
                command = run.call_args.args[0]
                self.assertNotIn("boldheadings=true", command)
                for prefix in ("fontenglish", "fontbengali", "fontarabic"):
                    selection = next(arg for arg in command if arg.startswith(prefix + "features="))
                    self.assertIn("BoldFont=", selection)
                self.assertIn("BoldFont={Amiri-Bold.ttf}", next(
                    arg for arg in command if arg.startswith("fontarabicfeatures=")
                ))

    @unittest.skipUnless(shutil.which("pandoc"), "Pandoc is required")
    def test_markdown_bold_survives_script_filter(self):
        result = subprocess.run(
            ["pandoc", "--from=markdown", "--to=latex", "--lua-filter", str(engine.LUA_FILTER_PATH)],
            input="Normal **bold** ***bold italic*** `**literal**`\n\n**বাংলা**\n\n**العربية**",
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        self.assertIn(r"\textbf{bold}", result.stdout)
        self.assertIn(r"\textbf{\emph{bold italic}}", result.stdout)
        self.assertIn(r"\textbf{\bn{বাংলা}}", result.stdout)
        self.assertIn(r"\textbf{\ar{العربية}}", result.stdout)
        self.assertIn(r"\texttt{**literal**}", result.stdout)

    @unittest.skipUnless(
        all(shutil.which(command) for command in ("pandoc", "xelatex", "pdffonts")),
        "Pandoc, XeLaTeX, and pdffonts are required",
    )
    def test_pdf_embeds_distinct_regular_and_bold_fonts(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bold.md"
            source.write_text(
                "Normal **bold** ***bold italic***\n\nবাংলা **বাংলা**\n\nالعربية **العربية**",
                encoding="utf-8",
            )
            for family in ("DejaVu Sans", "Georgia", "Noto Sans"):
                with self.subTest(family=family):
                    success, output = engine.convert_md_to_pdf(
                        source, output_directory=directory, english_font=family,
                        include_toc=False, bold_headings=False, log_func=lambda _message: None,
                    )
                    self.assertTrue(success, output)
                    fonts = subprocess.run(
                        ["pdffonts", output], capture_output=True, text=True, check=True,
                    ).stdout
                    self.assertIn("Amiri-Bold", fonts)
                    self.assertGreaterEqual(fonts.count("SolaimanLipiNormal"), 2)
                    if family == "Georgia":
                        self.assertIn("Georgia-Bold", fonts)
                    elif family == "DejaVu Sans":
                        self.assertGreaterEqual(fonts.count("DejaVuSans"), 2)
                    else:
                        self.assertGreaterEqual(fonts.count("NotoSans"), 2)


if __name__ == "__main__":
    unittest.main()