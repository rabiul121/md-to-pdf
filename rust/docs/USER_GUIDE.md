# PDF Creator Studio User Guide (Rust)

PDF Creator Studio converts Markdown, plain text, Word, EPUB, and MOBI documents
to PDF through Pandoc and XeLaTeX. Legacy `.doc` input requires LibreOffice;
`.mobi` input requires Calibre's `ebook-convert`.

## Getting Started

Install Pandoc and XeLaTeX before converting. The Windows package includes a
setup script; on Debian or Ubuntu run `setup.sh` from the extracted package to
install Pandoc, XeLaTeX, GUI libraries, and bundled fonts. From a source
checkout, use `rust/scripts/windows/setup.ps1` or
`bash rust/scripts/linux/setup.sh`, then build and launch the Rust app with
`cargo run --manifest-path rust/Cargo.toml --release`.

To convert a document, add it in **Documents**, adjust the options in the
settings views, choose an output folder and name, then select **Convert selected
to PDF**. To convert a draft without saving it first, use **Editor** and select
**Export PDF** or **Save PDF to…**.

## Document Editor

The **Editor** view accepts Markdown or literal plain text. **Open** loads an
`.md`, `.markdown`, or `.txt` file. **Save** writes the current file and **Save
As** chooses another path. New drafts can be exported directly. The status line
shows the current filename and marks unsaved changes.

Use **Undo** and **Redo** or Ctrl+Z and Ctrl+Y while the editor has focus. Before
opening another file, clearing a modified document, or closing the app, confirm
whether to save, discard, or cancel where applicable. **Plain Text** treats the
buffer contents literally during export.

## Markdown Formatting

The toolbar applies bold, italic, strikethrough, headings 1–6, bulleted and
numbered lists, task lists, blockquotes, inline code, fenced code blocks, links,
and horizontal rules. Select text first to wrap or transform it; with no
selection, formatting actions insert a placeholder where useful.

Fenced code blocks use triple backticks and may include a language name for
syntax highlighting:

```javascript
function calculateSum(a, b) {
  return a + b;
}
console.log(calculateSum(5, 10));
```

## Editor Preview and Resizing

Select **Live Preview** to show the rendered Markdown beside the editor. Drag
the divider to allocate between one quarter and three quarters of the available
width to the editor. The preview renders Markdown tables, lists, and code
blocks; **Plain Text** mode keeps the buffer literal for export.

## Documents and Conversion

Use **Add files…** to select documents or **Add folder…** to add supported
documents from a folder. Quick samples are available when the app's `input`
folder contains supported files. Filter the selected-file list by path or name,
remove individual files with **×**, or choose **Remove all**.

Supported extensions are `.md`, `.markdown`, `.txt`, `.doc`, `.docx`, `.epub`,
and `.mobi`. Batch conversion uses each input filename. Existing PDFs are not
overwritten; a numeric suffix is added to the next available output name. The
conversion log shows progress, warnings, and full Pandoc/XeLaTeX diagnostics.
Use **Copy log** to copy the complete log and **Open latest PDF** or **Open
output folder** to inspect results.

## Page and Geometry

- **Paper Size**: A4, Letter, A5, Legal, For Mobile, or For PC.
- **Orientation**: Portrait or Landscape.
- **Margin Preset**: a preset, page default, or a custom TeX dimension such as
  `20mm` or `0.75in`.
- **Decorative Page Border** draws a border around pages.
- **Output name and destination** sets the PDF name and output folder.
  A `~` prefix in a manually entered output folder expands to your home folder.

## Typography

Font selectors are searchable. Bundled families appear in the role's list and
installed system fonts are also available. The app supports English, heading,
Bengali, Arabic, and coding/monospace font choices; licensed MonoLisa and
Operator Mono faces are included when present in the package.

Choose Standard, Medium, Large, or Custom point size; set the line-spacing
multiplier and paragraph spacing; and configure bold or centered headings,
hyphenation, and first-line indentation. Font files are resolved directly when
bundled; installed families are resolved through the platform font system when
available.

## TOC and Page Numbers

Choose whether to include a table of contents, its design, language, and title
alignment. Page numbering has controls for display, number format, position,
and English or Bangla numerals. Front-matter numbering can be enabled with its
own style, format, position, and numeral language.

## Auto-Convert Watch Mode

In **Documents**, select exactly one existing file and enable **Auto-Convert
(Watch)**. The app converts it immediately and again when it detects a saved
change on disk. Disable the checkbox to stop watching. Watch mode runs only
while the app remains open.

## Configuration Profiles

The built-in profiles are Mobile, PC, English, and Bangla. Choose a profile and
select **Load profile** to apply it. Save current settings with **Save as New**;
update a selected profile with **Update profile**. User profiles can be deleted;
built-in profiles cannot. Settings and the last selected profile are stored in
the per-user app data directory (`%LOCALAPPDATA%` on Windows; `$XDG_DATA_HOME`
on Linux when set, otherwise `~/.local/share`). Existing Python profile files
are read when available, including partial profile overrides.

## Help and Search

Use **Search topics** to filter the topic list and guide text. Select a topic to
read it, or choose **Open full user guide** to open this Markdown file outside
the app.

## Keyboard Shortcuts

Shortcuts work while the Editor view is open. On macOS, use Command where the
table says Ctrl.

| Shortcut | Action |
| --- | --- |
| Ctrl+O | Open a Markdown or text file |
| Ctrl+S | Save the current file |
| Ctrl+Shift+S | Save as |
| Ctrl+N | New document (asks before discarding unsaved changes) |
| Ctrl+Z / Ctrl+Y | Undo / redo |
| Ctrl+B / Ctrl+I | Bold / italic selection |
| Ctrl+Shift+X | Strikethrough selection |
| Ctrl+K | Insert or wrap a link |
| Ctrl+Shift+C | Insert a fenced code block |
| Ctrl+Enter | Create a PDF |

Press Enter at the end of a Markdown list item or blockquote to continue its
prefix. Press Enter on an empty list item to leave the list.

## CLI

The separate `pdf-creator-studio-cli` binary supports batch conversion,
profiles, output directory and name overrides, literal plain text, file
watching, and an interactive wizard. Run
`cargo run --manifest-path rust/Cargo.toml --release --bin
pdf-creator-studio-cli -- --help` for command options. Add `--watch` for a
single input; `--watch-interval 5` checks for changes every five seconds.

The wizard lists supported documents from the app's `input` folder when
available and lets you select one, convert all, or enter custom paths. On
Windows, the installer adds **PDF Creator Studio CLI** to the Start menu. On
Linux, run `./cli.sh` from the extracted package to start the wizard, or pass
`--help` to see command options.

## Troubleshooting

- If Pandoc or XeLaTeX is missing, rerun the platform setup script and confirm
  `pandoc` and `xelatex` are available on `PATH`.
- If a chosen font is unavailable, select a bundled font or install the system
  font and refresh the platform font cache where needed.
- `.doc` conversion requires LibreOffice; `.mobi` conversion requires Calibre.
- On a conversion failure, copy the complete conversion log. The first LaTeX
  error usually identifies the cause of later cascading errors.
