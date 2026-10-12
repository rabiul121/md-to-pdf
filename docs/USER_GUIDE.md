# PDF Creator Studio User Guide

This guide covers the desktop application. The app converts Markdown, plain text, Word, EPUB, and MOBI files to PDF through Pandoc and XeLaTeX.

## First launch

On Windows, run the installer and allow it to install Python dependencies, Pandoc, and MiKTeX when prompted. If a dependency installer asks to finish or restart, follow that prompt, then launch **PDF Creator Studio** from the desktop or Start menu shortcut.

For a source checkout, run `scripts/windows/setup.bat` once, then launch with `run.bat`. Linux users can run `scripts/linux/setup.sh`, then `./run.sh`.

## Documents

1. Select **Choose File** for one source document, or **Batch Select** to convert multiple files.
2. Files in the project's `input` folder appear as quick-select chips.
3. **Output Folder** chooses where PDFs are written. **Custom Output Name** changes the output name for a single-file conversion; leave it blank to use the input filename.
4. Existing PDFs are kept. If a name already exists, the app adds a suffix such as `_1` rather than overwriting it.

Supported input extensions are `.md`, `.markdown`, `.txt`, `.doc`, `.docx`, `.epub`, and `.mobi`. Legacy `.doc` requires LibreOffice; `.mobi` requires Calibre's `ebook-convert` command.

## Editor

The **Editor** tab (the first tab) lets you write or paste Markdown or plain text and convert it to PDF directly, without creating a file first.

1. Paste or type your content into the editor.
2. Use the toolbar to apply Markdown formatting: bold, italic, strikethrough, headings 1-3, bulleted and numbered lists, block quotes, inline code, code blocks, links, and horizontal rules. Select text first, or place the cursor and click a button to insert a ready-to-type placeholder.
3. **Format** switches between Markdown and Plain Text. Plain Text converts your words literally with no Markdown parsing and disables the formatting toolbar.
4. **Open...** loads an existing `.md`, `.markdown`, or `.txt` file into the editor.
5. **Save** writes the document to its current file. **Save As...** saves the buffer to a new location. The status line next to the save buttons shows the current file and warns about unsaved changes.
6. **Clear / Close** empties the editor and closes the current file. If there are unsaved changes, the app asks for confirmation first.
7. The **eye icon** opens a live preview pane beside the editor. It refreshes as you type or apply formatting. Drag the vertical handle to resize the panes; both keep at least 30% of the available width. Press the eye icon again (or the X in the preview) to close it. Markdown preview supports fenced and indented code, task lists, nested lists, tables, quotes, and reference links. Code blocks use syntax highlighting that follows the light/dark app theme. Footnote references (`[^note]` with a `[^note]: ...` definition) appear as numbered references with a Footnotes section at the bottom. Plain Text mode previews the text literally.
8. The expand icon next to **Format** toggles the window between a normal and a maximized size, giving the editor more room.
9. **Export PDF** converts the buffer using all settings from the other tabs. A document loaded from disk is saved first so relative image paths keep resolving; an unsaved buffer is converted from a temporary file, so use **Save As...** if you want to keep your work.

The editor uses a compact icon-based file row and a single-line formatting toolbar (scroll horizontally if needed). Hover over an icon to see its action. The conversion log starts collapsed in the Editor tab to leave more room for writing; use its chevron to expand it. Other tabs expand the log automatically. The preview is not a PDF page-layout preview; exported pagination and typography still follow the conversion settings.

## Help

The **Help** tab (and the ? button in the title bar) opens the built-in help. Type in the **Search** box to filter the topic list by title, summary, or body text, then click a topic to read it. Topics are rendered with the same Markdown engine as the editor preview. The full manual also stays available in `docs/USER_GUIDE.md`.

## Page and geometry

- **Paper Size**: A4, Letter, A5, Legal, or the reading presets For Mobile and For PC.
- **Orientation**: Portrait or Landscape.
- **Margin Preset**: Choose a standard preset, use the selected paper size's default, or select Custom and enter a TeX dimension such as `20mm` or `0.75in`.
- **Decorative Page Border**: Draws a border around each page.

## Typography

- Each font selector is an editable, searchable dropdown. Type the first letters of a family (for example `A` then `Ar`) to filter the menu; the first match is highlighted and Enter or a click commits it. Project/bundled fonts appear first; installed system fonts follow alphabetically.
- **Bengali Font** and **Arabic Font** select script faces. The converter uses script coverage fallback for headings.
- **English Font** sets body text; **Heading Font** sets Latin headings independently.
- **Font Size Preset** supports Standard (11 pt), Medium (14 pt), Large (17 pt), and Custom. Custom values are in points.
- **Line Spacing Multiplier** controls baseline spacing. **Paragraph Spacing** adds space after paragraphs.
- **Bold Headings**, **Center Headings**, and **Hyphenation** toggle their respective formatting.
- **First Line Indent** enables paragraph indentation; **Indent Amount** accepts a TeX dimension.

Bundled font files are in `assets/fonts`. Some selectable commercial or operating-system fonts are not bundled and must already be installed. Verify font licenses before redistributing PDFs commercially.

## TOC and page numbers

- **Include Table of Contents** adds a TOC when the document has headings.
- **Beautify TOC** applies the selected TOC design.
- **TOC Language** selects English or Bangla title and digits where supported.
- **TOC Title Alignment** aligns the TOC heading. **TOC Design** selects Classic, Minimal, or Decorative.
- **Page Numbers** toggles main-document numbering. Position, format, and numeral language are selected separately.

## Profiles

- Choose a profile and press **Apply Profile** to load its settings.
- **Update Selected** saves the current controls over the selected built-in or custom profile. Built-in profiles can be updated, but cannot be deleted.
- **Save as New** stores current settings under a new custom name.
- **Delete** removes the selected custom profile only.
- The app remembers the selected profile, most recent settings, and theme between runs. Use the theme button to cycle **System**, **Light**, and **Dark**. System follows Windows appearance and responds when the system theme changes.

## Convert and watch

1. Choose **Convert Once** to convert the selected document(s) now.
2. Choose **Auto-Convert (Watch)** for one selected file. The app watches for saves and converts again when that file changes.
3. **Open Generated PDF** becomes available after a successful conversion. The folder button in the title bar opens the output directory.

The conversion log shows progress and errors. Use its copy button to copy the full log; individual entries can also be selected.

Syntax-highlighted code blocks are exported with Pandoc's matching highlight style: `tango` for the light theme and `breezedark` for the dark theme.

## Troubleshooting

- **Pandoc or XeLaTeX not found**: rerun the Windows installer/setup, or confirm both commands are available in PATH.
- **Font not found**: install the selected system font or choose one from the bundled project fonts. Restart the app after installing fonts.
- **DOC conversion fails**: install LibreOffice. **MOBI conversion fails**: install Calibre and ensure `ebook-convert` is on PATH.
- **Conversion failed**: copy the log and include it when asking for support. Look for the first LaTeX error above the final exit code; later messages are often consequences.

## Mobile app note

The Flet interface can be packaged for Android, but the current conversion engine launches desktop Pandoc and XeLaTeX executables. It therefore needs an Android-compatible conversion backend or a server-side conversion service before the APK can perform PDF conversions.
