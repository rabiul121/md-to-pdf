import unittest

import flet as ft

from src.core.markdown_preview import markdown_to_controls, prepare_markdown


class MarkdownPreviewTests(unittest.TestCase):
    def test_native_renderer_preserves_extended_markdown(self):
        source = (
            "# Heading\n\n````python\nprint('```')\n````\n\n"
            "    indented_code()\n\n- [x] Done\n- [ ] Pending\n"
            "  - Nested item\n\n> Quoted **text**\n\n"
            "| Column | Value |\n| --- | --- |\n| A | B |\n\n"
            "[Reference][docs]\n\n[docs]: https://example.com\n"
        )
        controls = markdown_to_controls(source)
        self.assertEqual(len(controls), 1)
        renderer = controls[0]
        self.assertIsInstance(renderer, ft.Markdown)
        self.assertEqual(renderer.value, source)
        self.assertEqual(renderer.extension_set, ft.MarkdownExtensionSet.GITHUB_WEB)
        self.assertTrue(renderer.selectable)
        self.assertTrue(renderer.auto_follow_links)
        self.assertIsNone(renderer.expand)

    def test_empty_preview(self):
        for source in (None, "", " \n\t"):
            self.assertEqual(markdown_to_controls(source), [])

    def test_code_theme_and_block_background_follow_theme(self):
        light = markdown_to_controls("```python\nprint(1)\n```", dark_theme=False)[0]
        dark = markdown_to_controls("```python\nprint(1)\n```", dark_theme=True)[0]
        self.assertEqual(light.code_theme, ft.MarkdownCodeTheme.GITHUB)
        self.assertEqual(dark.code_theme, ft.MarkdownCodeTheme.ATOM_ONE_DARK)
        self.assertEqual(light.md_style_sheet.codeblock_decoration.bgcolor, "#F6F8FA")
        self.assertEqual(dark.md_style_sheet.codeblock_decoration.bgcolor, "#282C34")

    def test_footnotes_numbered_by_reference_not_definition_order(self):
        source = "Second[^b], first[^a], repeat[^b].\n\n[^a]: Alpha\n[^b]: Beta"
        rendered = prepare_markdown(source)
        self.assertIn("Second**[1]**, first**[2]**, repeat**[1]**.", rendered)
        self.assertIn("### Footnotes\n\n1. Beta\n\n2. Alpha", rendered)
        self.assertNotIn("[^a]:", rendered)

    def test_multiline_notes_and_reference_links(self):
        rendered = prepare_markdown(
            "[^note]: **First** line\n    continuation\n\n"
            "    Second paragraph with [docs][link].\n\n"
            "Text[^note].\n\n[link]: https://example.com"
        )
        self.assertIn("Text**[1]**.", rendered)
        self.assertIn("1. **First** line\n    continuation\n\n    Second paragraph", rendered)
        self.assertIn("[link]: https://example.com", rendered)

    def test_footnotes_inside_code_and_escaped_references_are_literal(self):
        rendered = prepare_markdown(
            "````md\n[^fake]: Not a note\n```\n[^real]\n````\n\n"
            "    [^real]\n\n`[^real]` and ``code ` [^real]``\n"
            "`multiline\n[^real]`\n\\[^real] and missing[^missing]\n"
            "Actual[^real]\n\n[^real]: Real note"
        )
        self.assertIn("[^fake]: Not a note", rendered)
        self.assertIn("```\n[^real]\n````", rendered)
        self.assertIn("    [^real]", rendered)
        self.assertIn("`[^real]` and ``code ` [^real]``", rendered)
        self.assertIn("`multiline\n[^real]`", rendered)
        self.assertIn("\\[^real] and missing[^missing]", rendered)
        self.assertIn("Actual**[1]**", rendered)
        self.assertEqual(rendered.count("1. Real note"), 1)

    def test_nested_and_unused_notes(self):
        rendered = prepare_markdown(
            "Text[^a]\n\n[^a]: See also[^b]\n[^b]: Back[^a]\n[^unused]: Hidden"
        )
        self.assertIn("1. See also**[2]**", rendered)
        self.assertIn("2. Back**[1]**", rendered)
        self.assertNotIn("Hidden", rendered)


if __name__ == "__main__":
    unittest.main()