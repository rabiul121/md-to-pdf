import unittest
from pathlib import Path

from src.core import constants
from src.core import profiles
from src.core import engine
from src.cli import wizard
from src.ui import flet_app
from src import converter


class ModularArchitectureTests(unittest.TestCase):
    def test_constants_available(self):
        self.assertIn("A4", constants.PAGE_SIZES)
        self.assertIn("SolaimanLipi", constants.PROJECT_FONT_CHOICES["Bengali"])
        self.assertIn("Amiri", constants.PROJECT_FONT_CHOICES["Arabic"])
        self.assertTrue({"EB Garamond", "Georgia", "Sabon", "Adobe Garamond", "Minion Pro", "Alegreya", "Alegreya Sans", "Palatino Linotype", "Crimson Text", "Della Respira", "Sylfaen"}.issubset(constants.PROJECT_FONT_CHOICES["English"]))
        self.assertTrue({"Helvetica", "Arial", "Baskerville", "Libre Baskerville", "Futura", "Playfair Display"}.issubset(constants.HEADING_FONT_CHOICES))
        self.assertEqual(converter.PROJECT_FONT_CHOICES, constants.PROJECT_FONT_CHOICES)
        self.assertEqual(converter.HEADING_FONT_CHOICES, constants.HEADING_FONT_CHOICES)

    def test_removed_builtin_profiles_are_pruned(self):
        profs = profiles.load_profiles()
        self.assertEqual(
            set(constants.BUILT_IN_PROFILES),
            {"Mobile", "PC", "English", "Bangla"},
        )
        for name in constants.REMOVED_BUILT_IN_PROFILES:
            self.assertNotIn(name, profs)
        self.assertIn("Mobile", profs)
        self.assertIn("PC", profs)
        self.assertIn("English", profs)
        self.assertIn("Bangla", profs)

    def test_bundled_fonts_resolve_from_project_assets(self):
        for role, families in constants.BUNDLED_FONT_FILES.items():
            for family in families:
                with self.subTest(role=role, family=family):
                    resolved = engine.resolve_bundled_font(family, role)
                    self.assertIsNotNone(resolved)
                    self.assertNotIn("[", resolved[0])
                    self.assertNotIn("]", resolved[0])
                    self.assertTrue((Path(resolved[1]) / resolved[0]).is_file())
                    self.assertEqual(converter.resolve_bundled_font(family, role), resolved)

    def test_converter_reexports_constants_and_functions(self):
        self.assertEqual(converter.PAGE_SIZES, constants.PAGE_SIZES)
        self.assertTrue(callable(converter.convert_md_to_pdf))
        self.assertTrue(callable(converter.convert_many_to_pdf))
        self.assertTrue(callable(converter.launch_gui))
        self.assertTrue(callable(converter.cli_interactive_flow))

    def test_profile_defaults(self):
        profs = profiles.load_profiles()
        self.assertIn("Mobile", profs)
        self.assertIn("Bangla", profs)
        self.assertIn("English", profs)

    def test_existing_builtin_profile_can_be_updated(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_path = Path(temporary_directory) / "profiles.json"
            with patch.object(profiles, "PROFILE_PATH", profile_path):
                profiles.update_profile("English", {"english_font": "Georgia", "line_height": "1.25"})
                saved = profiles.load_profiles()["English"]

        self.assertEqual(saved["english_font"], "Georgia")
        self.assertEqual(saved["line_height"], "1.25")
        self.assertEqual(saved["heading_font"], constants.PROFILE_BASE_SETTINGS["heading_font"])

    def test_update_profile_rejects_unknown_names(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_path = Path(temporary_directory) / "profiles.json"
            with patch.object(profiles, "PROFILE_PATH", profile_path):
                with self.assertRaises(ValueError):
                    profiles.update_profile("Unknown Profile", {"line_height": "1.25"})

    def test_last_used_profile_selection_is_persisted(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_path = Path(temporary_directory) / "profiles.json"
            with patch.object(profiles, "PROFILE_PATH", profile_path):
                profiles.save_last_used_settings(
                    {"english_font": "Alegreya", "theme_mode": "system"},
                    selected_profile="Novel Preset",
                )
                last_used = profiles.load_last_used_settings()

        self.assertEqual(last_used["english_font"], "Alegreya")
        self.assertEqual(last_used["theme_mode"], "system")
        self.assertEqual(last_used["selected_profile"], "Novel Preset")

    def test_system_fonts_follow_project_fonts_when_no_tk_root_is_supplied(self):
        from unittest.mock import MagicMock, patch

        temporary_root = MagicMock()
        with patch("tkinter.Tk", return_value=temporary_root), patch(
            "tkinter.font.families", return_value=("Zeta Font", "Bundled Font", "Beta Font")
        ):
            fonts = engine.get_font_families(None, ["Project Font", "Bundled Font"])

        self.assertEqual(fonts, ["Project Font", "Bundled Font", "Beta Font", "Zeta Font"])
        temporary_root.withdraw.assert_called_once()
        temporary_root.destroy.assert_called_once()

    def test_latex_template_loads_soul_for_pandoc_underlines(self):
        template = constants.TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn(r"\usepackage{soul}", template)

    def test_flet_app_module_loadable(self):
        self.assertTrue(callable(flet_app.main))
        self.assertTrue(callable(flet_app.launch_flet_app))

    def test_app_is_named_pdf_creator_studio(self):
        import asyncio
        from unittest.mock import MagicMock, patch
        import flet as ft

        page = MagicMock(spec=ft.Page)
        page.overlay = []
        page.services = []
        page.window = MagicMock()
        page.add = lambda *controls: None
        page.update = MagicMock()

        with patch.object(flet_app, "load_last_used_settings", return_value={}), patch.object(
            flet_app, "save_last_used_settings"
        ):
            asyncio.run(flet_app.main(page))

        self.assertEqual(page.title, "PDF Creator Studio")
        self.assertEqual(page.appbar.title.value, "PDF Creator Studio")
        source = Path(flet_app.__file__).read_text(encoding="utf-8")
        self.assertNotIn("Markdown to PDF Studio", source)

    def test_engine_supports_plain_input_format_for_the_editor(self):
        import tempfile
        from unittest.mock import patch
        from src.core import engine

        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "draft.md"
            source.write_text("# Not a heading", encoding="utf-8")

            with patch.object(engine, "find_executable", side_effect=["pandoc", "xelatex"]), patch.object(
                engine.subprocess,
                "run",
                return_value=engine.subprocess.CompletedProcess([], 0, "", ""),
            ) as run:
                success, _result = engine.convert_md_to_pdf(
                    source,
                    input_format="plain",
                    log_func=lambda _message: None,
                )

        self.assertTrue(success)
        command = run.call_args.args[0]
        self.assertIn("--from=markdown+hard_line_breaks", command)
        self.assertNotIn("--from=plain", command)
        self.assertNotIn("--from=markdown", command)

    def test_engine_passes_theme_highlight_style_to_pandoc(self):
        import tempfile
        from unittest.mock import patch
        from src.core import engine

        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "code.md"
            source.write_text("```python\nprint(1)\n```", encoding="utf-8")

            with patch.object(engine, "find_executable", side_effect=["pandoc", "xelatex"]), patch.object(
                engine.subprocess,
                "run",
                return_value=engine.subprocess.CompletedProcess([], 0, "", ""),
            ) as run:
                success, _result = engine.convert_md_to_pdf(
                    source,
                    highlight_style="breezedark",
                    log_func=lambda _message: None,
                )

        self.assertTrue(success)
        self.assertIn("--highlight-style=breezedark", run.call_args.args[0])
        template_source = Path(engine.TEMPLATE_PATH).read_text(encoding="utf-8")
        self.assertIn("$highlighting-macros$", template_source)
        self.assertIn("$if(highlighting-macros)$", template_source)
        self.assertIn(r"\newenvironment{Shaded}", template_source)

    def test_flet_app_main_initializes_without_errors(self):
        import asyncio
        from unittest.mock import MagicMock, patch
        import flet as ft

        page = MagicMock(spec=ft.Page)
        page.overlay = []
        page.services = []
        page.window = MagicMock()
        added_controls = []
        page.add = lambda *controls: added_controls.extend(controls)
        page.update = MagicMock()

        with patch.object(flet_app, "load_last_used_settings", return_value={}), patch.object(
            flet_app, "save_last_used_settings"
        ):
            asyncio.run(flet_app.main(page))
        self.assertTrue(len(added_controls) > 0)
        self.assertIsInstance(page.services[0], ft.FilePicker)
        self.assertIsInstance(page.services[1], ft.Clipboard)
        log_container = added_controls[-1]
        dark_log_bg = log_container.bgcolor
        theme_btn = next(
            action
            for action in page.appbar.actions
            if str(getattr(action, "tooltip", "")).startswith("Theme:")
        )
        theme_btn.on_click(None)
        self.assertEqual(page.theme_mode, ft.ThemeMode.LIGHT)
        self.assertNotEqual(log_container.bgcolor, dark_log_bg)
        light_log_bg = log_container.bgcolor
        theme_btn.on_click(None)
        self.assertEqual(page.theme_mode, ft.ThemeMode.DARK)
        self.assertNotEqual(log_container.bgcolor, light_log_bg)
        page.theme_mode = ft.ThemeMode.SYSTEM
        page.platform_brightness = ft.Brightness.LIGHT
        page.on_platform_brightness_change(None)
        self.assertEqual(log_container.bgcolor, "#F1F3F5")

        def check_no_sets(ctrl):
            for k, v in getattr(ctrl, "__dict__", {}).items():
                self.assertNotIsInstance(v, set, f"Found set in control attribute {k}")
                if isinstance(v, list):
                    for item in v:
                        self.assertNotIsInstance(item, set, f"Found set inside list {k}")
                        if hasattr(item, "__dict__"):
                            check_no_sets(item)
                elif hasattr(v, "__dict__"):
                    check_no_sets(v)

        for c in added_controls:
            check_no_sets(c)


if __name__ == "__main__":
    unittest.main()
