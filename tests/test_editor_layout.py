import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import flet as ft

from src.ui import flet_app


class EditorLayoutTests(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock(spec=ft.Page)
        self.page.overlay = []
        self.page.services = []
        self.page.window = MagicMock()
        self.page.width = 1180
        self.added = []
        self.page.add = lambda *controls: self.added.extend(controls)
        with patch.object(flet_app, "load_last_used_settings", return_value={}):
            asyncio.run(flet_app.main(self.page))
        self.tabs = self.added[0]
        self.editor_tab = self.tabs.content.controls[1].controls[0]
        self.actions, self.toolbar, self.split = self.editor_tab.content.controls
        self.editor = self.split.controls[0].content

    def find_action(self, tooltip):
        return next(control for control in self.actions.controls if control.tooltip == tooltip)

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

    def test_compact_toolbar_and_full_height_editor(self):
        self.assertFalse(self.toolbar.wrap)
        self.assertEqual(self.toolbar.scroll, ft.ScrollMode.AUTO)
        self.assertTrue(all(button.height == 32 for button in self.toolbar.controls))
        self.assertTrue(self.editor.fit_parent_size)
        self.assertIsNone(self.editor.min_lines)
        self.assertEqual(self.split.vertical_alignment, ft.CrossAxisAlignment.STRETCH)
        self.assertEqual(self.added[-1].height, 48)
        self.tabs.selected_index = 1
        self.tabs.on_change(None)
        self.assertEqual(self.added[-1].height, 160)
        self.tabs.selected_index = 0
        self.tabs.on_change(None)
        self.assertEqual(self.added[-1].height, 48)
        self.added[-1].content.controls[0].controls[2].on_click(None)
        self.assertEqual(self.added[-1].height, 160)

    def test_preview_updates_on_every_keystroke_and_toolbar_action(self):
        self.find_action("Show Markdown preview").on_click(None)
        preview_body = self.split.controls[2].content.controls[-1]
        self.editor.value = "# First"
        self.editor.on_change(None)
        self.assertEqual(preview_body.controls[0].value, "# First")
        self.page.update.reset_mock()
        self.editor.value = "# Second"
        self.editor.on_change(None)
        self.page.update.assert_called()
        self.assertEqual(preview_body.controls[0].value, "# Second")
        self.editor.selection = ft.TextSelection(2, 8)
        self.toolbar.controls[0].on_click(None)
        self.assertEqual(preview_body.controls[0].value, "# **Second**")
        mode = next(control for control in self.actions.controls if isinstance(control, ft.Dropdown))
        mode.value = "Plain Text"
        mode.on_select(None)
        self.assertIsInstance(preview_body.controls[0], ft.Text)
        self.assertEqual(preview_body.controls[0].value, self.editor.value)
        self.assertTrue(all(button.disabled for button in self.toolbar.controls))

    def test_divider_responds_symmetrically_to_small_drag_updates(self):
        self.find_action("Show Markdown preview").on_click(None)
        editor, divider, preview = self.split.controls
        initial = editor.expand
        divider.on_horizontal_drag_update(SimpleNamespace(primary_delta=4))
        self.assertGreater(editor.expand, initial)
        divider.on_horizontal_drag_update(SimpleNamespace(primary_delta=-4))
        self.assertEqual(editor.expand, initial)
        divider.on_horizontal_drag_update(SimpleNamespace(primary_delta=10000))
        self.assertEqual((editor.expand, preview.expand), (700, 300))
        divider.on_horizontal_drag_update(SimpleNamespace(primary_delta=-10000))
        self.assertEqual((editor.expand, preview.expand), (300, 700))
        divider.on_horizontal_drag_update(SimpleNamespace(primary_delta=None))
        self.assertEqual(editor.expand, 300)

    def test_font_selectors_are_searchable_with_bundled_fonts_first(self):
        tab_views = self.tabs.content.controls[1]
        typography = tab_views.controls[3]
        font_dropdowns = []

        def collect(control):
            if isinstance(control, ft.Dropdown) and control.label and "Font" in control.label and "Size" not in control.label:
                font_dropdowns.append(control)
            for child in getattr(control, "controls", []) or []:
                collect(child)
            child = getattr(control, "content", None)
            if child is not None:
                collect(child)

        collect(typography)
        self.assertEqual(len(font_dropdowns), 4)
        for dropdown in font_dropdowns:
            self.assertTrue(dropdown.editable)
            self.assertTrue(dropdown.enable_filter)
            self.assertTrue(dropdown.enable_search)
            self.assertEqual(dropdown.leading_icon, ft.Icons.SEARCH)
        self.assertEqual(font_dropdowns[0].options[0].key, "SolaimanLipi")
        self.assertEqual(font_dropdowns[1].options[0].key, "Amiri")
        self.assertIsNone(self.find_control(typography, lambda c: isinstance(c, ft.TextField) and c.label == "Search fonts"))

        english = next(dropdown for dropdown in font_dropdowns if dropdown.label == "English Font")
        previous = english.value
        english.on_focus(SimpleNamespace(control=english, data=None))
        self.assertIsNone(english.value)
        english.on_text_change(SimpleNamespace(control=english, data="not a real font"))
        self.assertIsNone(english.value)
        english.on_blur(SimpleNamespace(control=english, data=None))
        self.assertEqual(english.value, previous)

        english.on_focus(SimpleNamespace(control=english, data=None))
        english.on_text_change(SimpleNamespace(control=english, data="DejaVu Sans"))
        self.assertEqual(english.value, "DejaVu Sans")


if __name__ == "__main__":
    unittest.main()