"""Native Markdown rendering shared by the editor preview and Help tab.

Flet handles Markdown block structure. Pandoc-style footnotes are normalized
to numbered endnotes, without changing the editor buffer.
"""

import re

import flet as ft


_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_NOTE_RE = re.compile(r"^ {0,3}\[\^([^\]]+)\]:[ \t]*(.*)$")
_REFERENCE_RE = re.compile(r"(?<!\\)\[\^([^\]]+)\]")
_CODE_SPAN_RE = re.compile(r"(`+).*?\1(?!`)", re.DOTALL)


def _prose_lines(lines):
    """Yield indexes outside fenced and four-space/tab-indented code."""
    fence = None
    for index, line in enumerate(lines):
        marker = _FENCE_RE.match(line)
        if fence:
            if (
                marker
                and marker[1][0] == fence[0]
                and len(marker[1]) >= len(fence)
                and not marker[2].strip()
            ):
                fence = None
            continue
        if marker:
            fence = marker[1]
        elif not line.startswith(("    ", "\t")):
            yield index


def prepare_markdown(markdown_text):
    """Resolve footnotes in first-reference order, preserving code and whitespace.

    Definitions may precede references and contain indented continuations.
    Unresolved and escaped references remain literal.
    """
    lines = (markdown_text or "").splitlines()
    definitions = {}
    removed = set()
    for index in _prose_lines(lines):
        if index in removed:
            continue
        match = _NOTE_RE.match(lines[index])
        if not match:
            continue
        label, first_line = match.groups()
        note_lines = [first_line]
        removed.add(index)
        cursor = index + 1
        while cursor < len(lines):
            line = lines[cursor]
            if line.startswith(("    ", "\t")):
                note_lines.append(line[4:] if line.startswith("    ") else line[1:])
                removed.add(cursor)
                cursor += 1
            elif (
                not line.strip()
                and cursor + 1 < len(lines)
                and lines[cursor + 1].startswith(("    ", "\t"))
            ):
                note_lines.append("")
                removed.add(cursor)
                cursor += 1
            else:
                break
        definitions.setdefault(label, "\n".join(note_lines))

    if not definitions:
        return markdown_text or ""

    used = []

    def replace_reference(match):
        label = match[1]
        if label not in definitions:
            return match[0]
        if label not in used:
            used.append(label)
        return f"**[{used.index(label) + 1}]**"

    def replace_prose(text):
        pieces = []
        position = 0
        for match in _CODE_SPAN_RE.finditer(text):
            pieces.append(_REFERENCE_RE.sub(replace_reference, text[position:match.start()]))
            pieces.append(match[0])
            position = match.end()
        pieces.append(_REFERENCE_RE.sub(replace_reference, text[position:]))
        return "".join(pieces)

    def replace_body(body):
        prose = set(_prose_lines(body))
        cursor = 0
        while cursor < len(body):
            if cursor not in prose:
                cursor += 1
                continue
            end = cursor + 1
            while end in prose:
                end += 1
            body[cursor:end] = replace_prose("\n".join(body[cursor:end])).split("\n")
            cursor = end
        return body

    body = replace_body([line for index, line in enumerate(lines) if index not in removed])
    notes = []
    cursor = 0
    while cursor < len(used):
        note = replace_body(definitions[used[cursor]].split("\n"))
        notes.append(f"{cursor + 1}. {note[0]}")
        notes.extend(f"    {line}" if line else "" for line in note[1:])
        notes.append("")
        cursor += 1
    if notes:
        body.extend(["", "---", "", "### Footnotes", ""] + notes)
    return "\n".join(body)


def markdown_to_controls(markdown_text, code_theme=None, dark_theme=False):
    """Return a content-sized Markdown control for a scrolling parent.

    ``code_theme`` selects the syntax-highlighting palette. The caller can pass
    the theme resolved from the page so the preview follows light/dark mode;
    when omitted, the GitHub light palette keeps standalone callers stable.
    """
    if not (markdown_text or "").strip():
        return []
    if code_theme is None:
        code_theme = ft.MarkdownCodeTheme.ATOM_ONE_DARK if dark_theme else ft.MarkdownCodeTheme.GITHUB
    codeblock_background = "#282C34" if dark_theme else "#F6F8FA"
    return [
        ft.Markdown(
            value=prepare_markdown(markdown_text),
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=code_theme,
            selectable=True,
            auto_follow_links=True,
            shrink_wrap=True,
            fit_content=False,
            code_style_sheet=ft.MarkdownStyleSheet(
                code_text_style=ft.TextStyle(font_family="monospace", size=13),
            ),
            md_style_sheet=ft.MarkdownStyleSheet(
                p_text_style=ft.TextStyle(size=14),
                code_text_style=ft.TextStyle(font_family="monospace", size=13),
                block_spacing=10,
                list_indent=24,
                codeblock_padding=12,
                codeblock_decoration=ft.BoxDecoration(
                    bgcolor=codeblock_background,
                    border_radius=ft.BorderRadius.all(6),
                ),
            ),
        )
    ]