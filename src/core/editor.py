"""Pure text-buffer editing operations for the built-in document editor.

Each helper receives the current buffer text plus a selection range and
returns ``(new_text, new_selection_start, new_selection_end)`` so the UI can
apply the result without knowing anything about Markdown syntax itself.
"""

import re
import string

HEADING_PATTERN = re.compile(r"\A#{1,6}\s+")
LIST_MARKER_PATTERN = re.compile(r"\A(?:[-*+] |\d+\. )")
QUOTE_PATTERN = re.compile(r"\A> ?")
AUTO_CONTINUE_PATTERN = re.compile(
    r"\A(?P<indent>[ \t]*)(?:(?P<task>[-*+] \[[ xX]\] )|(?P<bullet>[-*+] )|(?P<number>\d+\. )|(?P<quote>> ?))(?P<body>.*)\Z"
)


def continue_markdown_block(previous, current, caret):
    """Continue a Markdown list or quote after an Enter key insertion.

    Returns ``(new_text, new_caret)`` when the current edit consists of a
    single inserted newline and the caret is immediately after it; otherwise
    returns ``None`` so normal typing is left untouched.
    """
    if len(current) != len(previous) + 1:
        return None
    prefix = 0
    limit = min(len(previous), len(current))
    while prefix < limit and previous[prefix] == current[prefix]:
        prefix += 1
    if current[prefix:prefix + 1] != "\n":
        return None
    if previous[prefix:] != current[prefix + 1:]:
        return None
    newline_caret = prefix + 1
    if caret != newline_caret:
        return None

    line_start = current.rfind("\n", 0, prefix) + 1
    previous_line = current[line_start:prefix]
    match = AUTO_CONTINUE_PATTERN.match(previous_line)
    if not match:
        return None

    body = match.group("body")
    if not body.strip():
        # Enter on a marker-only line exits the list/quote cleanly.
        updated = current[:line_start] + current[prefix:]
        return updated, line_start

    indent = match.group("indent")
    if match.group("task"):
        marker = "- [ ] "
    elif match.group("bullet"):
        marker = match.group("bullet")
    elif match.group("number"):
        number = int(match.group("number").strip()[:-1]) + 1
        marker = f"{number}. "
    else:
        marker = match.group("quote")
    continuation = indent + marker
    updated = current[:newline_caret] + continuation + current[newline_caret:]
    return updated, newline_caret + len(continuation)


def escape_plain_text(text):
    """Escape ASCII punctuation so plain text renders literally in Pandoc.

    Pandoc has no plain-text reader, so plain documents are converted as
    Markdown with every ASCII punctuation character backslash-escaped. The
    conversion pairs this with ``markdown+hard_line_breaks`` so line structure
    from the original text is preserved.
    """
    return "".join(
        "\\" + char if char in string.punctuation else char for char in text
    )


def _line_bounds(value, start, end):
    """Expand a selection range so it covers whole lines."""
    start = max(0, min(start, len(value)))
    end = max(start, min(end, len(value)))
    line_start = value.rfind("\n", 0, start) + 1
    newline_index = value.find("\n", end)
    line_end = len(value) if newline_index == -1 else newline_index
    return line_start, line_end


def wrap_text(value, start, end, prefix, suffix=None, placeholder=""):
    """Wrap the selection with ``prefix``/``suffix`` markers.

    Wrapping is reversible: when the markers already surround either the
    selection itself or the text just inside it, they are removed instead. A
    collapsed selection inserts the markers around ``placeholder`` and selects
    the placeholder so the user can start typing immediately.
    """
    if suffix is None:
        suffix = prefix
    selected = value[start:end]
    if (
        len(selected) >= len(prefix) + len(suffix)
        and selected.startswith(prefix)
        and selected.endswith(suffix)
    ):
        inner = selected[len(prefix):len(selected) - len(suffix)]
        return value[:start] + inner + value[end:], start, start + len(inner)
    if (
        start >= len(prefix)
        and value[start - len(prefix):start] == prefix
        and value[end:end + len(suffix)] == suffix
    ):
        text = value[:start - len(prefix)] + selected + value[end + len(suffix):]
        return text, start - len(prefix), start - len(prefix) + len(selected)
    if start == end:
        text = value[:start] + prefix + placeholder + suffix + value[end:]
        inner_start = start + len(prefix)
        return text, inner_start, inner_start + len(placeholder)
    text = value[:start] + prefix + selected + suffix + value[end:]
    inner_start = start + len(prefix)
    return text, inner_start, inner_start + len(selected)


def toggle_line_markers(value, start, end, exact_pattern, strip_pattern, marker_factory):
    """Add a line-start marker to the selected lines, or remove it.

    When every non-empty selected line already starts with a marker matching
    ``exact_pattern`` the markers are removed (toggle off). Otherwise existing
    markers matching ``strip_pattern`` are replaced by the marker produced by
    ``marker_factory(line_number)``.
    """
    line_start, line_end = _line_bounds(value, start, end)
    lines = value[line_start:line_end].split("\n")
    non_empty = [line for line in lines if line.strip()]
    remove_mode = bool(non_empty) and all(exact_pattern.match(line) for line in non_empty)
    result = []
    line_number = 0
    for line in lines:
        if not line.strip():
            result.append(line)
            continue
        if remove_mode:
            result.append(exact_pattern.sub("", line, count=1))
        else:
            line_number += 1
            result.append(marker_factory(line_number) + strip_pattern.sub("", line, count=1))
    new_segment = "\n".join(result)
    text = value[:line_start] + new_segment + value[line_end:]
    return text, line_start, line_start + len(new_segment)


def heading_producer(level):
    """Toggle a heading of the given level on the selected lines."""
    marker = "#" * level + " "
    exact = re.compile(r"\A" + re.escape(marker))

    def producer(value, start, end):
        return toggle_line_markers(
            value, start, end, exact, HEADING_PATTERN, lambda _number, m=marker: m
        )

    return producer


def bullet_producer():
    """Toggle a bulleted list marker on the selected lines."""
    exact = re.compile(r"\A- ")

    def producer(value, start, end):
        return toggle_line_markers(
            value, start, end, exact, LIST_MARKER_PATTERN, lambda _number: "- "
        )

    return producer


def ordered_list_producer():
    """Toggle a numbered list marker, renumbering the selected lines."""
    exact = re.compile(r"\A\d+\. ")

    def producer(value, start, end):
        return toggle_line_markers(
            value, start, end, exact, LIST_MARKER_PATTERN, lambda number: f"{number}. "
        )

    return producer


def task_list_producer():
    """Toggle Markdown task-list markers on the selected lines."""
    exact = re.compile(r"\A- \[[ xX]\] ")

    def producer(value, start, end):
        return toggle_line_markers(
            value,
            start,
            end,
            exact,
            LIST_MARKER_PATTERN,
            lambda _number: "- [ ] ",
        )

    return producer


def quote_producer():
    """Toggle a block quote marker on the selected lines."""
    exact = re.compile(r"\A> ")

    def producer(value, start, end):
        return toggle_line_markers(
            value, start, end, exact, QUOTE_PATTERN, lambda _number: "> "
        )

    return producer


def bold_producer():
    return lambda value, start, end: wrap_text(
        value, start, end, "**", placeholder="bold text"
    )


def italic_producer():
    return lambda value, start, end: wrap_text(
        value, start, end, "*", placeholder="italic text"
    )


def strikethrough_producer():
    return lambda value, start, end: wrap_text(
        value, start, end, "~~", placeholder="strikethrough"
    )


def inline_code_producer():
    return lambda value, start, end: wrap_text(
        value, start, end, "`", placeholder="code"
    )


def code_block_producer():
    return lambda value, start, end: wrap_text(
        value, start, end, "\n```\n", "\n```\n", placeholder="code block"
    )


def link_producer():
    url_placeholder = "https://example.com"

    def producer(value, start, end):
        if start == end:
            return wrap_text(
                value,
                start,
                end,
                "[",
                f"]({url_placeholder})",
                placeholder="link text",
            )
        selected = value[start:end]
        text = value[:start] + f"[{selected}]({url_placeholder})" + value[end:]
        url_start = start + len(selected) + 3
        return text, url_start, url_start + len(url_placeholder)

    return producer


def horizontal_rule_producer():
    def producer(value, start, end):
        block = "\n\n---\n"
        text = value[:end] + block + value[end:]
        position = end + len(block)
        return text, position, position

    return producer
