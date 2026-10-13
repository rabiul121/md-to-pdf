import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import flet as ft

from src.core import constants, profiles
from src.ui import flet_app


class UiRedesignTests(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock(spec=ft.Page)
        self.page.overlay = []
        self.page.services = []
        self.page.window = MagicMock()
        self.page.width = 1180
        self.page.update = MagicMock()
        self.added = []
        self.page.add = lambda *controls: self.added.extend(controls)
        self.save_mock = patch.object(flet_app, "save_last_used_settings").start()
        self.load_mock = patch.object(
            flet_app, "load_last_used_settings", return_value={}
        ).start()
        asyncio.run(flet_app.main(self.page))
        self.addCleanup(patch.stopall)

        self.body = self.added[0]
        self.sidebar = self.body.controls[0]
        self.view_holder = self.body.controls[2]
        self.log_container = self.added[-1]

    def find_control(self, root, predicate):
        if predicate(root):
            return root
        for child in getattr(root, "controls", []) or []:
            found = self.find_control(child, predicate)
            if found is not None:
                return found
        for attr in ("content", "tab_views"):
            child = getattr(root, attr, None)
            if child is not None:
                found = self.find_control(child, predicate)
                if found is not None:
                    return found
        return None

    def navigate(self, key):
        item = self.find_control(
            self.sidebar, lambda c: getattr(c, "data", None) == key
        )
        self.assertIsNotNone(item, f"Sidebar item {key!r} not found")
        item.on_click(None)
        return self.view_holder.content

    def test_appbar_hosts_conversion_controls_with_dynamic_primary_action(self):
        actions = self.page.appbar.actions
        primary = actions[0]
        self.assertIsInstance(primary, ft.FilledButton)
        self.assertFalse(primary.visible)
        self.assertEqual(primary.text, "Export PDF")
        self.assertIsInstance(actions[1], ft.OutlinedButton)
        open_label = getattr(actions[1], "text", None) or getattr(
            actions[1], "content", None
        )
        self.assertEqual(open_label, "Open Generated PDF")
        self.assertEqual(actions[2].tooltip, "Open Output Folder")
        self.assertIsInstance(actions[3], ft.SegmentedButton)
        fullscreen_btn = actions[-2]
        self.assertEqual(fullscreen_btn.icon, ft.Icons.FULLSCREEN)
        self.assertTrue(
            str(getattr(actions[-1], "tooltip", "")).startswith("Theme:")
        )
        self.assertIsNone(
            self.find_control(
                self.page.appbar,
                lambda c: "Help" in str(getattr(c, "tooltip", "")),
            )
        )

        self.navigate("documents")
        self.assertTrue(primary.visible)
        self.assertEqual(primary.text, "Convert to PDF")
        self.navigate("editor")
        self.assertFalse(primary.visible)
        self.assertEqual(primary.text, "Export PDF")

    def test_sidebar_shrinks_and_keeps_preference_children_nested(self):
        self.assertIsNotNone(
            self.find_control(
                self.sidebar, lambda c: getattr(c, "data", None) == "geometry"
            )
        )

        collapse = self.find_control(
            self.sidebar,
            lambda c: getattr(c, "tooltip", None) == "Collapse sidebar",
        )
        collapse.on_click(None)
        self.assertEqual(self.sidebar.width, 64)
        self.assertIsNone(
            self.find_control(
                self.sidebar, lambda c: getattr(c, "data", None) == "geometry"
            )
        )
        self.assertIsNone(
            self.find_control(
                self.sidebar,
                lambda c: isinstance(c, ft.Text) and c.value == "Editor",
            )
        )

        preferences = self.find_control(
            self.sidebar, lambda c: getattr(c, "data", None) == "preferences"
        )
        preferences.on_click(None)
        self.assertEqual(self.sidebar.width, 216)
        self.assertIsNotNone(
            self.find_control(
                self.sidebar, lambda c: getattr(c, "data", None) == "geometry"
            )
        )

    def test_conversion_log_is_scoped_to_editor_and_documents(self):
        self.assertTrue(self.log_container.visible)
        self.navigate("help")
        self.assertFalse(self.log_container.visible)
        self.navigate("profiles")
        self.assertFalse(self.log_container.visible)
        self.navigate("documents")
        self.assertTrue(self.log_container.visible)
        self.assertEqual(self.log_container.height, 160)
        self.navigate("editor")
        self.assertTrue(self.log_container.visible)
        self.assertEqual(self.log_container.height, 48)

    def test_help_topics_pane_resizes_and_search_results_stay_available(self):
        self.navigate("help")
        pane = self.find_control(
            self.view_holder,
            lambda c: getattr(c, "data", None) == "help-topics-pane",
        )
        divider = self.find_control(
            self.view_holder,
            lambda c: getattr(c, "data", None) == "help-topics-divider",
        )
        search_results = self.find_control(
            self.view_holder,
            lambda c: getattr(c, "data", None) == "help-search-results",
        )
        search_field = self.find_control(
            self.view_holder,
            lambda c: isinstance(c, ft.TextField) and c.label == "Search help topics",
        )
        self.assertIsNotNone(pane)
        self.assertIsNotNone(divider)
        self.assertIsNotNone(search_results)
        self.assertIsNotNone(search_field)

        initial_width = pane.width
        divider.on_horizontal_drag_update(SimpleNamespace(primary_delta=40))
        self.assertEqual(pane.width, initial_width + 40)
        divider.on_horizontal_drag_update(SimpleNamespace(primary_delta=10000))
        self.assertEqual(pane.width, 380)

        search_field.value = "preview"
        search_field.on_change(SimpleNamespace(data="preview"))
        self.assertTrue(search_results.visible)
        self.assertGreater(len(search_results.controls), 0)

        toggle = self.find_control(
            self.view_holder,
            lambda c: getattr(c, "tooltip", None) == "Collapse the Topics pane",
        )
        toggle.on_click(None)
        self.assertFalse(pane.visible)
        self.assertTrue(search_results.visible)

        first_result = search_results.controls[0]
        first_result.content.on_click(None)
        self.assertFalse(search_results.visible)
        self.assertEqual(search_field.value, "preview")
        details = self.find_control(
            self.view_holder,
            lambda c: getattr(c, "data", None) == "help-details",
        )
        self.assertIsNotNone(details)
        self.assertGreater(len(details.content.controls), 0)

        clear_btn = self.find_control(
            self.view_holder,
            lambda c: getattr(c, "tooltip", None) == "Clear search",
        )
        self.assertIsNotNone(clear_btn)
        self.assertTrue(clear_btn.visible)
        clear_btn.on_click(None)
        self.assertEqual(search_field.value, "")
        self.assertFalse(clear_btn.visible)
        self.assertFalse(search_results.visible)

        toggle = self.find_control(
            self.view_holder,
            lambda c: getattr(c, "tooltip", None) == "Show the Topics pane",
        )
        toggle.on_click(None)
        self.assertTrue(pane.visible)

    def test_theme_defaults_to_system_and_persists_explicit_choice(self):
        self.assertEqual(self.page.theme_mode, ft.ThemeMode.SYSTEM)
        self.assertEqual(flet_app.resolve_theme_mode("not-a-mode"), ft.ThemeMode.SYSTEM)
        self.assertEqual(flet_app.resolve_theme_mode("dark"), ft.ThemeMode.DARK)
        self.assertEqual(flet_app.resolve_theme_mode(None), ft.ThemeMode.SYSTEM)

        theme_btn = next(
            action
            for action in self.page.appbar.actions
            if str(getattr(action, "tooltip", "")).startswith("Theme:")
        )
        theme_btn.on_click(None)
        self.assertEqual(self.page.theme_mode, ft.ThemeMode.LIGHT)
        saved_settings = self.save_mock.call_args.args[0]
        self.assertEqual(saved_settings["theme_mode"], "light")

        with patch.object(
            flet_app,
            "load_last_used_settings",
            return_value={"theme_mode": "definitely-invalid"},
        ):
            page = MagicMock(spec=ft.Page)
            page.overlay = []
            page.services = []
            page.window = MagicMock()
            page.width = 1180
            page.update = MagicMock()
            page.add = lambda *_controls: None
            asyncio.run(flet_app.main(page))
        self.assertEqual(page.theme_mode, ft.ThemeMode.SYSTEM)

    def test_legacy_builtin_profile_entries_are_filtered_and_guards_apply(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_path = Path(temporary_directory) / "profiles.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "Minimal": {"line_height": "1.0"},
                        "Book Print - Georgia": {"english_font": "Georgia"},
                        "My Custom Profile": {"line_height": "1.5"},
                        "_last_used": {"theme_mode": "system"},
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(profiles, "PROFILE_PATH", profile_path):
                loaded = profiles.load_profiles()
                self.assertNotIn("Minimal", loaded)
                self.assertNotIn("Book Print - Georgia", loaded)
                self.assertIn("My Custom Profile", loaded)
                with self.assertRaises(ValueError):
                    profiles.save_profile("Minimal", {"line_height": "1.0"})

        self.assertEqual(
            set(constants.BUILT_IN_PROFILES),
            {"Mobile", "PC", "English", "Bangla"},
        )


if __name__ == "__main__":
    unittest.main()