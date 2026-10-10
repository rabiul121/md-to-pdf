import unittest

from src.core import editor


class WrapTextTests(unittest.TestCase):
    def test_bold_wraps_selected_text(self):
        text, start, end = editor.wrap_text(
            "hello world", 0, 5, "**", placeholder="bold text"
        )
        self.assertEqual(text, "**hello** world")
        self.assertEqual((start, end), (2, 7))
        self.assertEqual(text[start:end], "hello")

    def test_bold_unwraps_when_applied_to_already_wrapped_text(self):
        text, start, end = editor.wrap_text("**hello** world", 2, 7, "**")
        self.assertEqual(text, "hello world")
        self.assertEqual((start, end), (0, 5))

    def test_bold_unwraps_when_markers_are_inside_the_selection(self):
        text, start, end = editor.wrap_text("**hello** world", 0, 9, "**")
        self.assertEqual(text, "hello world")
        self.assertEqual(text[start:end], "hello")

    def test_collapsed_selection_inserts_selected_placeholder(self):
        text, start, end = editor.wrap_text("", 0, 0, "*", placeholder="italic text")
        self.assertEqual(text, "*italic text*")
        self.assertEqual(text[start:end], "italic text")

    def test_wrapping_in_the_middle_of_a_line_keeps_surrounding_text(self):
        text, start, end = editor.wrap_text(
            "say hello now", 4, 9, "`", placeholder="code"
        )
        self.assertEqual(text, "say `hello` now")
        self.assertEqual(text[start:end], "hello")


class LineMarkerTests(unittest.TestCase):
    def test_heading_added_to_every_selected_line(self):
        text, start, end = editor.heading_producer(1)("Title\nBody", 0, 9)
        self.assertEqual(text, "# Title\n# Body")
        self.assertEqual(text[start:end], "# Title\n# Body")

    def test_heading_level_is_replaced_not_removed(self):
        text, _start, _end = editor.heading_producer(1)("## Old", 0, 6)
        self.assertEqual(text, "# Old")

    def test_same_heading_level_toggles_off(self):
        text, _start, _end = editor.heading_producer(2)("## Old", 0, 6)
        self.assertEqual(text, "Old")

    def test_line_markers_expand_to_the_whole_line(self):
        text = "Intro\nTitle\nTail"
        new_text, start, end = editor.heading_producer(2)(text, 8, 10)
        self.assertEqual(new_text, "Intro\n## Title\nTail")
        self.assertEqual(new_text[start:end], "## Title")

    def test_bullet_list_toggle_on_and_off(self):
        producer = editor.bullet_producer()
        text, _start, _end = producer("one\ntwo", 0, 7)
        self.assertEqual(text, "- one\n- two")
        toggled, _start, _end = producer("- one\n- two", 0, 11)
        self.assertEqual(toggled, "one\ntwo")

    def test_ordered_list_renumbers_selected_lines(self):
        text, _start, _end = editor.ordered_list_producer()("alpha\nbeta\ngamma", 0, 16)
        self.assertEqual(text, "1. alpha\n2. beta\n3. gamma")

    def test_ordered_list_converts_bullets_and_renumbers(self):
        text, _start, _end = editor.ordered_list_producer()("- one\n- two", 0, 11)
        self.assertEqual(text, "1. one\n2. two")

    def test_quote_toggle_on_and_off(self):
        producer = editor.quote_producer()
        text, _start, _end = producer("said", 0, 4)
        self.assertEqual(text, "> said")
        toggled, _start, _end = producer("> said", 0, 6)
        self.assertEqual(toggled, "said")

    def test_empty_lines_are_left_untouched(self):
        text, _start, _end = editor.bullet_producer()("one\n\ntwo", 0, 8)
        self.assertEqual(text, "- one\n\n- two")


class InsertTests(unittest.TestCase):
    def test_link_wraps_selection_and_selects_the_url_placeholder(self):
        text, start, end = editor.link_producer()("see docs", 4, 8)
        self.assertEqual(text, "see [docs](https://example.com)")
        self.assertEqual(text[start:end], "https://example.com")

    def test_link_collapsed_cursor_inserts_link_text_placeholder(self):
        text, start, end = editor.link_producer()("", 0, 0)
        self.assertEqual(text, "[link text](https://example.com)")
        self.assertEqual(text[start:end], "link text")

    def test_horizontal_rule_inserts_a_block_after_the_cursor(self):
        text, start, end = editor.horizontal_rule_producer()("above", 5, 5)
        self.assertEqual(text, "above\n\n---\n")
        self.assertEqual((start, end), (len(text), len(text)))

    def test_code_block_wraps_the_selection_in_fences(self):
        text, start, end = editor.code_block_producer()("print(1)", 0, 8)
        self.assertEqual(text, "\n```\nprint(1)\n```\n")
        self.assertEqual(text[start:end], "print(1)")

    def test_strikethrough_and_inline_code_round_trip(self):
        struck, s_start, s_end = editor.strikethrough_producer()("gone", 0, 4)
        self.assertEqual(struck, "~~gone~~")
        restored, _start, _end = editor.strikethrough_producer()(
            struck, s_start, s_end
        )
        self.assertEqual(restored, "gone")

        coded, c_start, c_end = editor.inline_code_producer()("x = 1", 0, 5)
        self.assertEqual(coded, "`x = 1`")
        uncoded, _start, _end = editor.inline_code_producer()(coded, c_start, c_end)
        self.assertEqual(uncoded, "x = 1")


class PlainTextEscapeTests(unittest.TestCase):
    def test_escapes_markdown_metacharacters(self):
        self.assertEqual(
            editor.escape_plain_text("# Title\n- item **x**"),
            "\\# Title\n\\- item \\*\\*x\\*\\*",
        )

    def test_leaves_letters_digits_and_newlines_untouched(self):
        text = "Hello 123\nsecond line"
        self.assertEqual(editor.escape_plain_text(text), text)

    def test_escapes_backslashes_before_punctuation(self):
        self.assertEqual(editor.escape_plain_text("a\\b"), "a\\\\b")


if __name__ == "__main__":
    unittest.main()