"""Built-in help topics rendered in the Help tab of the Flet application.

Each topic is a dict with ``title``, ``summary``, ``keywords`` and a
``body`` written in Markdown so it can be rendered by
``src.core.markdown_preview``.
"""

HELP_TOPICS = [
    {
        "title": "Getting Started",
        "summary": "First launch and the conversion workflow.",
        "keywords": "start install setup launch convert quick start",
        "body": "\n".join(
            [
                "## Getting Started",
                "",
                "PDF Creator Studio converts **Markdown**, **plain text**, Word, EPUB and MOBI",
                "files to PDF using Pandoc and XeLaTeX.",
                "",
                "1. Install the dependencies with the setup script for your platform.",
                "2. Open the **Documents** tab and pick a file, or write in the **Editor** tab.",
                "3. Adjust page, font and TOC options in the other tabs.",
                "4. Press **Convert to PDF** in the bottom bar.",
                "",
                "Use the **Search** box at the top of this Help tab to find any topic.",
            ]
        ),
    },
    {
        "title": "Document Editor",
        "summary": "Open, edit, save and convert documents in the editor.",
        "keywords": "editor open save save as clear close new file buffer markdown plain text",
        "body": "\n".join(
            [
                "## Document Editor",
                "",
                "The **Editor** tab lets you write Markdown or plain text and convert it",
                "without creating a file first.",
                "",
                "- **Open...** loads an existing `.md`, `.markdown` or `.txt` file.",
                "- **Save** writes the current file. **Save As...** picks a new location.",
                "- **Clear / Close** empties the editor and closes the current file.",
                "- **Convert Editor to PDF** converts the buffer with the current settings.",
                "",
                "The status line shows the file name and warns about *unsaved changes*.",
            ]
        ),
    },
    {
        "title": "Editor Preview and Resizing",
        "summary": "Live Markdown preview and resizing the editor area.",
        "keywords": "preview live markdown split resize expand drag divider fullscreen maximize",
        "body": "\n".join(
            [
                "## Editor Preview and Resizing",
                "",
                "- **Preview** shows a live rendering of the Markdown you are editing.",
                "  It refreshes as you type, so it always mirrors the editor buffer.",
                "- Drag the **vertical handle** between the editor and the preview to",
                "  resize the two panes.",
                "- **Expand Editor** toggles the window between a normal and a maximized size.",
                "",
                "> The preview only renders Markdown. In Plain Text mode it shows the raw text.",
            ]
        ),
    },
    {
        "title": "Markdown Formatting",
        "summary": "The Markdown syntax supported by the editor and preview.",
        "keywords": "markdown syntax bold italic heading list quote code link rule toolbar format",
        "body": "\n".join(
            [
                "## Markdown Formatting",
                "",
                "The toolbar applies Markdown for you:",
                "",
                "- **Bold** and *italic*, ~~strikethrough~~",
                "- Headings 1 to 3",
                "- Bulleted and numbered lists",
                "- Block quotes and `inline code`",
                "- [Links](https://pandoc.org) and horizontal rules",
                "",
                "Fenced code blocks are supported too:",
                "",
                "```markdown",
                "# A heading",
                "**bold** text with a [link](https://example.com)",
                "- a bullet",
                "```",
                "",
                "Select text first, or place the cursor and press a button to insert a",
                "ready-to-type placeholder.",
            ]
        ),
    },
    {
        "title": "Help and Search",
        "summary": "Using this help window.",
        "keywords": "help search topics find guide user guide documentation",
        "body": "\n".join(
            [
                "## Help and Search",
                "",
                "This tab is the built-in help. The search box filters topics as you type,",
                "matching titles, summaries, keywords and body text.",
                "",
                "Click a topic on the left to read it on the right. The full manual stays",
                "available in `docs/USER_GUIDE.md`.",
            ]
        ),
    },
    {
        "title": "Page and Geometry",
        "summary": "Paper size, orientation, margins and page borders.",
        "keywords": "page size paper a4 letter a5 legal orientation portrait landscape margin border",
        "body": "\n".join(
            [
                "## Page and Geometry",
                "",
                "- **Paper Size**: A4, Letter, A5, Legal, or the For Mobile and For PC presets.",
                "- **Orientation**: Portrait or Landscape.",
                "- **Margin Preset**: a standard preset, the paper size default, or Custom",
                "  with a TeX dimension such as `20mm` or `0.75in`.",
                "- **Decorative Page Border**: draws a border around each page.",
            ]
        ),
    },
    {
        "title": "Typography",
        "summary": "Fonts, sizes, spacing and heading style.",
        "keywords": "font typography size bengali arabic english heading line spacing indent bold headings hyphenation",
        "body": "\n".join(
            [
                "## Typography",
                "",
                "- **Search fonts** filters all four font menus as you type. Project fonts",
                "  appear first, installed system fonts follow.",
                "- **Bengali Font** and **Arabic Font** select script faces.",
                "- **English Font** sets body text; **Heading Font** sets Latin headings.",
                "- **Font Size Preset**: Standard, Medium, Large or Custom (points).",
                "- **Line Spacing Multiplier** and **Paragraph Spacing** control rhythm.",
                "- **Bold Headings**, **Center Headings**, **Hyphenation** and",
                "  **First Line Indent** toggle formatting.",
            ]
        ),
    },
    {
        "title": "TOC and Page Numbers",
        "summary": "Table of contents and numbering options.",
        "keywords": "toc table of contents page numbers language design beautify alignment",
        "body": "\n".join(
            [
                "## TOC and Page Numbers",
                "",
                "- **Include Table of Contents** adds a TOC when the document has headings.",
                "- **Beautify TOC** applies the selected TOC design.",
                "- **TOC Language** selects English or Bangla titles and digits.",
                "- **Page Numbers** toggles numbering; position, format and numeral",
                "  language are selected separately.",
            ]
        ),
    },
    {
        "title": "Auto-Convert Watch Mode",
        "summary": "Re-convert automatically when the source file changes.",
        "keywords": "watch auto convert monitor reload mode continuous",
        "body": "\n".join(
            [
                "## Auto-Convert Watch Mode",
                "",
                "Switch the bottom bar to **Auto-Convert (Watch)** and press the convert",
                "button. The app then re-compiles the selected file every time it changes on",
                "disk, so you can keep an editor open beside the PDF.",
                "",
                "Press the button again to stop watching.",
            ]
        ),
    },
    {
        "title": "Configuration Profiles",
        "summary": "Save and reuse conversion settings.",
        "keywords": "profile configuration save apply update delete settings preset",
        "body": "\n".join(
            [
                "## Configuration Profiles",
                "",
                "- Choose a profile and press **Apply Profile** to load its settings.",
                "- **Save as New** stores the current settings under a new name.",
                "- **Update Selected** overwrites the selected profile.",
                "- Built-in profiles can be updated but not deleted.",
            ]
        ),
    },
    {
        "title": "Troubleshooting",
        "summary": "Missing dependencies and conversion errors.",
        "keywords": "error pandoc xelatex latex missing install fails debug problem log",
        "body": "\n".join(
            [
                "## Troubleshooting",
                "",
                "- **Pandoc not found**: install Pandoc and restart the app.",
                "- **XeLaTeX not found**: install MiKTeX or TeX Live with xetex.",
                "- `.doc` input needs LibreOffice; `.mobi` needs Calibre's `ebook-convert`.",
                "- Read the **Conversion Log** at the bottom of the window; every failed",
                "  run prints the exact command line that was executed.",
            ]
        ),
    },
]


def search_help_topics(query):
    """Return topics matching *query* (empty query returns all topics)."""
    text = (query or "").strip().lower()
    if not text:
        return list(HELP_TOPICS)
    return [
        topic
        for topic in HELP_TOPICS
        if text
        in f"{topic['title']} {topic['summary']} {topic['keywords']} {topic['body']}".lower()
    ]

