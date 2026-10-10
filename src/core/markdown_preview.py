"""Markdown-to-Flet renderer used by the editor preview pane and the Help tab.

This is intentionally a small renderer for the subset of Markdown that the
editor toolbar produces: headings, emphasis, strikethrough, inline code, code
blocks, links, images, block quotes, bullet/numbered lists and horizontal
rules.  It renders to native Flet controls so the preview works in both the
desktop and web Flet runtimes without an HTML embedding control.
"""

import re

import flet as ft

_FENCE_RE = re.compile(r"^\s*(```+|~~~+)\s*(\S*)\s*$")
_HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.*)$")
_HRULE_RE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
_BULLET_RE = re.compile(r"^\s*([-*+])\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
_PARAGRAPH_START_RE = re.compile(r"^\s*(#|>|[-*+]\s|\d+[.)]\s|```|~~~)")

# Inline tokens, ordered so code spans win over emphasis markers.
_INLINE_TOKEN_RE = re.compile(
    r"`(?P<code>[^`]+)`"
    r"|!\[(?P<img_alt>[^\]]*)\]\((?P<img_src>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
    r"|\[(?P<link_text>[^\]]+)\]\((?P<link_href>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
    r"|\*\*\*(?P<bi>[^\n]+?)\*\*\*"
    r"|\*\*(?P<bold>[^*\n]+?)\*\*"
    r"|__(?P<bold_under>[^_\n]+?)__"
    r"|~~(?P<strike>[^~\n]+?)~~"
    r"|\*(?P<italic>[^*\n]+?)\*"
    r"|_(?P<italic_under>[^_\n]+?)_"
)

_BASE_STYLE = ft.TextStyle()
_CODE_STYLE = ft.TextStyle(font_family="monospace", color=ft.Colors.TEAL_200)


def inline_markdown(text, link_color=ft.Colors.BLUE_400):
    """Convert inline Markdown in *text* to a list of ``ft.TextSpan``s."""
    spans = []
    position = 0

    def _plain(chunk):
        if chunk:
            spans.append(ft.TextSpan(chunk, _BASE_STYLE))

    for match in _INLINE_TOKEN_RE.finditer(text or ""):
        _plain(text[position : match.start()])
        position = match.end()
        groups = match.groupdict()

        if groups["code"] is not None:
            spans.append(ft.TextSpan(groups["code"], _CODE_STYLE))
        elif groups["img_alt"] is not None:
            spans.append(ft.TextSpan(f"[image: {groups['img_alt'] or groups['img_src']}]", _BASE_STYLE))
        elif groups["link_text"] is not None:
            spans.append(
                ft.TextSpan(
                    groups["link_text"],
                    ft.TextStyle(
                        color=link_color, decoration=ft.TextDecoration.UNDERLINE
                    ),
                    url=groups["link_href"],
                )
            )
        elif groups["bi"] is not None:
            spans.append(
                ft.TextSpan(
                    groups["bi"],
                    ft.TextStyle(weight=ft.FontWeight.BOLD, italic=True),
                )
            )
        elif groups["bold"] is not None or groups["bold_under"] is not None:
            spans.append(
                ft.TextSpan(
                    groups["bold"] or groups["bold_under"],
                    ft.TextStyle(weight=ft.FontWeight.BOLD),
                )
            )
        elif groups["strike"] is not None:
            spans.append(
                ft.TextSpan(
                    groups["strike"],
                    ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH),
                )
            )
        elif groups["italic"] is not None or groups["italic_under"] is not None:
            spans.append(
                ft.TextSpan(
                    groups["italic"] or groups["italic_under"],
                    ft.TextStyle(italic=True),
                )
            )

    _plain(text[position:] if text else "")
    return spans


def _text_block(spans, size=14, **kwargs):
    """Single-line fast path uses ft.Text's value; otherwise use spans."""
    return ft.Text(spans=spans, size=size, selectable=True, expand=True, **kwargs)


def _code_block(code_lines):
    return ft.Container(
        content=ft.Text(
            "\n".join(code_lines),
            font_family="monospace",
            size=13,
            selectable=True,
        ),
        bgcolor=ft.Colors.BLUE_GREY_900,
        border_radius=8,
        padding=12,
        expand=True,
    )


def _list_row(marker, text):
    return ft.Row(
        [
            ft.Text(marker, size=14),
            _text_block(inline_markdown(text)),
        ],
        spacing=6,
        tight=True,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )


def markdown_to_controls(markdown_text):
    """Render Markdown text into a list of Flet controls."""
    controls = []
    lines = (markdown_text or "").splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)[0] * 3
            index += 1
            code_lines = []
            while index < len(lines) and not lines[index].strip().startswith(marker):
                code_lines.append(lines[index])
                index += 1
            index += 1  # consume the closing fence
            controls.append(_code_block(code_lines))
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            sizes = {1: 26, 2: 22, 3: 19, 4: 17, 5: 15, 6: 14}
            controls.append(
                _text_block(
                    inline_markdown(heading.group(2).strip()),
                    size=sizes[level],
                    weight=ft.FontWeight.BOLD,
                )
            )
            index += 1
            continue

        if _HRULE_RE.match(line):
            controls.append(ft.Divider())
            index += 1
            continue

        if line.lstrip().startswith(">"):
            quote_lines = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(lines[index].strip().lstrip(">").strip())
                index += 1
            controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            _text_block(inline_markdown(quote), italic=True)
                            for quote in quote_lines
                        ],
                        spacing=2,
                        tight=True,
                    ),
                    border=ft.Border(left=ft.BorderSide(3, ft.Colors.BLUE_300)),
                    padding={"left": 10},
                    expand=True,
                )
            )
            continue

        bullet = _BULLET_RE.match(line)
        numbered = _NUMBERED_RE.match(line)
        if bullet or numbered:
            items = []
            while index < len(lines):
                current_bullet = _BULLET_RE.match(lines[index])
                current_numbered = _NUMBERED_RE.match(lines[index])
                if current_bullet:
                    items.append(_list_row("•", current_bullet.group(2)))
                    index += 1
                elif current_numbered:
                    items.append(
                        _list_row(f"{current_numbered.group(1)}.", current_numbered.group(2))
                    )
                    index += 1
                else:
                    break
            controls.append(ft.Column(items, spacing=4, tight=True, expand=True))
            continue

        paragraph = [stripped]
        index += 1
        while (
            index < len(lines)
            and lines[index].strip()
            and not _PARAGRAPH_START_RE.match(lines[index])
        ):
            paragraph.append(lines[index].strip())
            index += 1
        controls.append(_text_block(inline_markdown(" ".join(paragraph))))

    return controls

