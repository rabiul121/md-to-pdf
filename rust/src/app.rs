use crate::{config::{self, Settings, ARABIC_FONTS, BENGALI_FONTS, CODE_FONTS, ENGLISH_FONTS, HEADING_FONTS, SUPPORTED_EXTENSIONS}, converter, editor::{self, History, Snapshot}, profiles};
use eframe::egui::{self, RichText};
use std::{fs, path::PathBuf, sync::mpsc::{self, Receiver, Sender}, thread, time::{Duration, SystemTime}};

#[derive(Clone, Copy, PartialEq, Eq)] enum View { Editor, Documents, PageLayout, Typography, Toc, Profiles, Help }
enum WorkerMessage { Log(String), Finished(Vec<converter::ConvertResult>) }

pub struct StudioApp {
    view: View,
    settings: Settings,
    persisted_settings: Settings,
    last_persist_attempt: Option<std::time::Instant>,
    editor: String,
    editor_path: Option<PathBuf>,
    saved_text: String,
    plain_text: bool,
    preview: bool,
    preview_split: f32,
    preview_cache: egui_commonmark::CommonMarkCache,
    history: History,
    editor_id: egui::Id,
    previous_text: String,
    selection: (usize, usize),
    pending_cursor_restore: bool,
    focus_editor_on_start: bool,
    editor_focused: bool,
    confirm_clear: bool,
    confirm_close: bool,
    confirm_open: bool,
    pending_open: Option<PathBuf>,
    selected_files: Vec<PathBuf>,
    input_filter: String,
    font_search: [String; 5],
    profiles: std::collections::BTreeMap<String, Settings>,
    profile_name: String,
    persisted_profile_name: String,
    new_profile_name: String,
    log_lines: Vec<String>,
    log_expanded: bool,
    busy: bool,
    messages_tx: Sender<WorkerMessage>,
    messages_rx: Receiver<WorkerMessage>,
    last_results: Vec<converter::ConvertResult>,
    status: String,
    dark: bool,
    auto_watch: bool,
    watched_path: Option<PathBuf>,
    watched_modified: Option<SystemTime>,
    last_watch_convert: SystemTime,
    help_search: String,
    help_selected: String,
    help_cache: egui_commonmark::CommonMarkCache,
}

impl StudioApp {
    pub fn new(cc: &eframe::CreationContext<'_>) -> Self {
        let last=profiles::last_used();
        let (settings, saved_profile) = last.clone().unwrap_or_default();
        let mut all_profiles = profiles::load_profiles();
        let selected = saved_profile.filter(|name| all_profiles.contains_key(name)).or_else(|| Some("Mobile".into())).unwrap_or_else(|| "PC".into());
        if !all_profiles.contains_key(&selected) { all_profiles.insert("PC".into(), Settings::default()); }
        let mut settings = if last.is_some() { settings } else { all_profiles.get(&selected).cloned().unwrap_or_default() };
        let dark = match settings.theme_mode.as_str() { "light" => false, "dark" => true, _ => system_theme_is_dark() };
        settings.theme_mode=match settings.theme_mode.as_str(){"light"=>"light","dark"=>"dark",_=>"system"}.into();
        // PDFs have a white page background, so keep code highlighting print-friendly
        // even when the application interface is using its dark theme.
        settings.highlight_style="tango".into();
        let persisted_settings=settings.clone();
        let persisted_profile_name=selected.clone();
        let (messages_tx, messages_rx) = mpsc::channel();
        let mut app = Self {
            view: View::Editor, settings, persisted_settings, last_persist_attempt: None, editor: String::new(), editor_path: None,
            saved_text: String::new(), plain_text: false, preview: false, preview_split: 0.5, preview_cache: Default::default(),
            history: History::new(200), editor_id: egui::Id::new("studio-markdown-editor"),
            previous_text: String::new(), selection: (0, 0), pending_cursor_restore: false, focus_editor_on_start: true, editor_focused: false,
            confirm_clear: false, confirm_close: false, confirm_open: false, pending_open: None,
            selected_files: Vec::new(),
            input_filter: String::new(), font_search: std::array::from_fn(|_| String::new()), profiles: all_profiles, profile_name: selected,
            persisted_profile_name, new_profile_name: String::new(), log_lines: Vec::new(), log_expanded: true,
            busy: false, messages_tx, messages_rx, last_results: Vec::new(), status: "Ready".into(),
            dark, auto_watch: false, watched_path: None, watched_modified: None,
            last_watch_convert: SystemTime::UNIX_EPOCH, help_search: String::new(),
            help_selected: "Getting Started".into(), help_cache: Default::default(),
        };
        apply_system_font(&cc.egui_ctx);
        apply_visual_style(&cc.egui_ctx, app.dark);
        app.push_log("[STUDIO] PDF Creator Studio (Rust) initialized.");
        app.push_log(format!("[STUDIO] Resource root: {}", config::resource_dir().display()));
        app
    }

    fn push_log(&mut self, line: impl Into<String>) {
        let stamp = chrono::Local::now().format("%H:%M:%S");
        self.log_lines.push(format!("[{stamp}] {}", line.into()));
        if self.log_lines.len() > 2000 { self.log_lines.drain(..500); }
    }

    fn poll_worker(&mut self) {
        while let Ok(message) = self.messages_rx.try_recv() {
            match message {
                WorkerMessage::Log(line) => self.push_log(line),
                WorkerMessage::Finished(results) => {
                    self.busy = false;
                    let succeeded = results.iter().filter(|r| r.output.is_some()).count();
                    self.status = if succeeded == results.len() && succeeded > 0 { format!("Succeeded ({succeeded}/{})", results.len()) } else { format!("Finished with errors ({succeeded}/{})", results.len()) };
                    self.last_results = results;
                }
            }
        }
    }

    fn start_conversion(&mut self, inputs: Vec<PathBuf>, forced_name: Option<String>, input_format: Option<&'static str>, cleanup_inputs: Vec<PathBuf>) {
        if self.busy || inputs.is_empty() { return; }
        self.save_last_settings();
        self.busy = true; self.status = "Converting…".into();
        let tx = self.messages_tx.clone(); let settings = self.settings.clone();
        thread::spawn(move || {
            let mut log = |line| { let _ = tx.send(WorkerMessage::Log(line)); };
            let results = inputs.iter().map(|input| {
                let output_name = forced_name.as_deref();
                let mut file_settings=settings.clone();
                if inputs.len()>1 { file_settings.output_name.clear(); }
                match converter::convert_one(input, &file_settings, input_format, output_name, &mut log) {
                    Ok(output) => converter::ConvertResult { input: input.clone(), output: Some(output), error: None },
                    Err(error) => { log(format!("[ERROR] {error:#}")); converter::ConvertResult { input: input.clone(), output: None, error: Some(error.to_string()) } }
                }
            }).collect();
            for path in cleanup_inputs { let _ = fs::remove_file(path); }
            let _ = tx.send(WorkerMessage::Finished(results));
        });
    }

    fn open_editor(&mut self) {
        let Some(path) = rfd::FileDialog::new().add_filter("Documents", &["md", "markdown", "txt"]).pick_file() else { return; };
        if self.editor!=self.saved_text {
            self.pending_open=Some(path);
            self.confirm_open=true;
        } else { self.load_editor(path); }
    }

    fn load_editor(&mut self, path: PathBuf) {
        match fs::read_to_string(&path) {
            Ok(text) => { self.editor = text.strip_prefix('\u{feff}').unwrap_or(&text).to_owned(); self.saved_text = self.editor.clone(); self.previous_text = self.editor.clone(); self.editor_path = Some(path.clone()); self.plain_text = path.extension().is_some_and(|e| e.eq_ignore_ascii_case("txt")); self.selection = (0, 0); self.pending_cursor_restore=true; self.focus_editor_on_start=true; self.history.clear(); self.push_log(format!("[EDITOR] Opened '{}' in the editor.", path.file_name().unwrap_or_default().to_string_lossy())); }
            Err(error) => self.push_log(format!("[ERROR] Could not open '{}': {error}", path.display())),
        }
    }

    fn save_editor(&mut self, save_as: bool) -> bool {
        let mut path = if save_as || self.editor_path.is_none() {
            let mut dialog = rfd::FileDialog::new().add_filter("Markdown", &["md", "markdown", "txt"]);
            if let Some(current) = &self.editor_path { dialog = dialog.set_file_name(current.file_name().unwrap_or_default().to_string_lossy()); }
            match dialog.save_file() { Some(path) => path, None => return false }
        } else { self.editor_path.clone().unwrap() };
        if path.extension().is_none() { path.set_extension(if self.plain_text { "txt" } else { "md" }); }
        match fs::write(&path, &self.editor) {
            Ok(()) => { self.editor_path = Some(path.clone()); self.saved_text = self.editor.clone(); self.push_log(format!("[EDITOR] Saved '{}'.", path.file_name().unwrap_or_default().to_string_lossy())); true }
            Err(error) => { self.push_log(format!("[ERROR] Could not save document: {error}")); false },
        }
    }

    fn export_editor(&mut self) {
        if self.editor.trim().is_empty() || self.busy { return; }
        let temporary_input=self.editor_path.is_none();
        let input=if let Some(path)=self.editor_path.clone() {
            if self.editor!=self.saved_text && !self.save_editor(false) {
                self.push_log("[ERROR] Could not save the editor document; PDF export was cancelled.");
                return;
            }
            path
        } else {
            let unique=chrono::Local::now().format("%Y%m%d-%H%M%S-%f");
            let path=std::env::temp_dir().join(format!("editor-draft-{unique}.{}",if self.plain_text{"txt"}else{"md"}));
            if let Err(error)=fs::write(&path,&self.editor) {
                self.push_log(format!("[ERROR] Could not create temporary draft: {error}"));
                return;
            }
            self.push_log("[EDITOR] Converted from a temporary buffer. Use Save As to keep a copy on disk.");
            path
        };
        let forced=input.file_stem().map(|s|s.to_string_lossy().to_string());
        let cleanup=if temporary_input { vec![input.clone()] } else { Vec::new() };
        self.start_conversion(vec![input],forced,if self.plain_text{Some("plain")}else{None},cleanup);
    }

    fn clear_editor(&mut self) {
        self.editor.clear(); self.saved_text.clear(); self.editor_path = None;
        self.previous_text.clear(); self.selection = (0, 0); self.pending_cursor_restore=true; self.focus_editor_on_start=true; self.history.clear(); self.plain_text = false;
    }

    fn editor_snapshot(&self) -> Snapshot { Snapshot { text: self.editor.clone(), selection: self.selection } }

    fn transform_editor(&mut self, kind: &str) {
        if self.plain_text { return; }
        let before = self.editor_snapshot();
        let (next, range) = match kind {
            "bold" => editor::wrap_selection(&self.editor, self.selection, "**", "**", "bold text"),
            "italic" => editor::wrap_selection(&self.editor, self.selection, "*", "*", "italic text"),
            "strike" => editor::wrap_selection(&self.editor, self.selection, "~~", "~~", "strikethrough"),
            "inline" => editor::wrap_selection(&self.editor, self.selection, "`", "`", "code"),
            "codeblock" => editor::wrap_selection(&self.editor, self.selection, "\n```\n", "\n```\n", "code block"),
            "link" => editor::insert_link(&self.editor, self.selection),
            "rule" => { let pos = self.selection.1.min(self.editor.len()); let mut s=self.editor.clone(); s.insert_str(pos, "\n\n---\n"); let p=pos+6; (s,(p,p)) },
            "bullet" => editor::transform_lines(&self.editor, self.selection, "-"),
            "number" => editor::ordered_list(&self.editor, self.selection),
            "task" => editor::transform_lines(&self.editor, self.selection, "- [ ]"),
            "quote" => editor::transform_lines(&self.editor, self.selection, ">"),
            _ if kind.starts_with('h') => editor::heading(&self.editor, self.selection, kind[1..].parse().unwrap_or(1)),
            _ => return,
        };
        self.editor = next; self.selection = range;
        self.history.record(before, &self.editor_snapshot()); self.previous_text = self.editor.clone();
        self.pending_cursor_restore = true;
    }

    fn apply_snapshot(&mut self, snapshot: Snapshot) {
        self.editor = snapshot.text; self.selection = snapshot.selection; self.previous_text = self.editor.clone();
        self.pending_cursor_restore = true;
    }

    fn undo(&mut self) { let current=self.editor_snapshot(); if let Some(s)=self.history.undo(current) { self.apply_snapshot(s); } }
    fn redo(&mut self) { let current=self.editor_snapshot(); if let Some(s)=self.history.redo(current) { self.apply_snapshot(s); } }

    fn add_files(&mut self) {
        if let Some(files) = rfd::FileDialog::new().add_filter("Supported documents", SUPPORTED_EXTENSIONS).pick_files() {
            for path in files { if !self.selected_files.contains(&path) { self.selected_files.push(path); } }
        }
    }

    fn markdown_preview(&mut self, ui: &mut egui::Ui) {
        if self.plain_text { ui.add(egui::Label::new(&self.editor).selectable(true).wrap()); return; }
        if self.editor.trim().is_empty() { ui.weak("Nothing to preview yet. Start typing in the editor."); return; }
        ui.style_mut().url_in_tooltip = true;
        let viewer=egui_commonmark::CommonMarkViewer::new();
        let viewer=if self.dark { viewer.syntax_theme_dark("base16-ocean.dark") } else { viewer.syntax_theme_light("InspiredGitHub") };
        viewer.show(ui, &mut self.preview_cache, &self.editor);
    }

    fn top_bar(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            ui.label(RichText::new(self.view_title()).size(18.0).strong());
            ui.separator();
            ui.label(RichText::new("PDF Creator Studio").weak());
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            let theme_label=match self.settings.theme_mode.as_str(){"system"=>"System theme","light"=>"Dark theme","dark"=>"Light theme",_=>"System theme"};
            if ui.button(theme_label).on_hover_text(format!("Theme: {} (click to change)",self.settings.theme_mode)).clicked() {
                self.settings.theme_mode=match self.settings.theme_mode.as_str(){"system"=>"light","light"=>"dark",_=>"system"}.into();
                if self.settings.theme_mode=="system" { self.dark=system_theme_is_dark(); } else { self.dark=self.settings.theme_mode=="dark"; }
                self.settings.highlight_style="tango".into();
                apply_visual_style(ui.ctx(), self.dark);
            }
            ui.label(RichText::new(if self.busy { "● Converting" } else { "● Ready" }).color(if self.busy { egui::Color32::from_rgb(241, 177, 76) } else { egui::Color32::from_rgb(64, 190, 146) }));
            });
        });
    }

    fn view_title(&self) -> &'static str {
        match self.view { View::Editor=>"Editor", View::Documents=>"Documents", View::PageLayout=>"Page layout", View::Typography=>"Typography", View::Toc=>"TOC & page numbers", View::Profiles=>"Profiles", View::Help=>"Help" }
    }

    fn side_nav(&mut self, ui: &mut egui::Ui) {
        ui.vertical(|ui| {
            ui.add_space(2.0);
            ui.horizontal(|ui| {
                egui::Frame::new().fill(egui::Color32::from_rgb(24,164,156)).corner_radius(egui::CornerRadius::same(7)).inner_margin(egui::Margin::symmetric(7,5)).show(ui,|ui|ui.label(RichText::new("PDF").size(12.0).strong().color(egui::Color32::WHITE)));
                ui.vertical(|ui| { ui.label(RichText::new("PDF Creator").size(17.0).strong()); ui.label(RichText::new("DOCUMENT STUDIO").size(9.0).weak()); });
            });
            ui.add_space(12.0);
            let scroll_height=(ui.available_height()-112.0).max(100.0);
            egui::ScrollArea::vertical().id_salt("sidebar-navigation").max_height(scroll_height).show(ui,|ui| {
                ui.label(RichText::new("WORKSPACE").size(10.0).strong().weak());
                ui.add_space(5.0);
                for (glyph, fallback, label, view) in [("\u{e70f}","ED","Editor",View::Editor),("\u{e8a5}","DOC","Documents",View::Documents)] {
                    if nav_button(ui,self.view==view,glyph,fallback,label) { self.view=view; }
                }
                ui.add_space(12.0);
                ui.label(RichText::new("DESIGN").size(10.0).strong().weak());
                ui.add_space(5.0);
                for (glyph, fallback, label, view) in [("\u{e8a5}","PAGE","Page layout",View::PageLayout),("\u{e8d2}","FONT","Typography",View::Typography),("\u{e8ef}","TOC","TOC & numbers",View::Toc)] {
                    if nav_button(ui,self.view==view,glyph,fallback,label) { self.view=view; }
                }
                ui.add_space(12.0);
                ui.label(RichText::new("PREFERENCES").size(10.0).strong().weak());
                ui.add_space(5.0);
                for (glyph, fallback, label, view) in [("\u{e77b}","SET","Profiles",View::Profiles),("\u{e897}","?","Help & guide",View::Help)] {
                    if nav_button(ui,self.view==view,glyph,fallback,label) { self.view=view; }
                }
            });
            egui::Frame::new().fill(ui.visuals().faint_bg_color).corner_radius(egui::CornerRadius::same(8)).inner_margin(egui::Margin::same(10)).show(ui, |ui| {
                ui.label(RichText::new("ACTIVE PROFILE").size(9.0).strong().weak());
                ui.label(RichText::new(&self.profile_name).strong());
                ui.label(RichText::new(if self.busy { "Working on your PDF…" } else { "Ready to create" }).size(11.0).weak());
            });
        });
    }

    fn editor_view(&mut self, ui: &mut egui::Ui) {
        egui::Frame::group(ui.style()).corner_radius(egui::CornerRadius::same(9)).inner_margin(egui::Margin::symmetric(12, 8)).show(ui,|ui|ui.horizontal_wrapped(|ui| {
            if ui.button("Open").clicked() { self.open_editor(); }
            if ui.button("Save").clicked() { self.save_editor(false); }
            if ui.button("Save as").clicked() { self.save_editor(true); }
            if ui.button("Clear").clicked() {
                if self.editor_path.is_some() || self.editor!=self.saved_text { self.confirm_clear=true; }
                else { self.clear_editor(); }
            }
            ui.separator();
            if ui.add_enabled(self.history.can_undo(), egui::Button::new("Undo")).clicked() { self.undo(); }
            if ui.add_enabled(self.history.can_redo(), egui::Button::new("Redo")).clicked() { self.redo(); }
            ui.checkbox(&mut self.plain_text, "Plain Text");
            if ui.button(if self.preview { "Hide preview" } else { "Live preview" }).clicked() { self.preview=!self.preview; }
            let label = self.editor_path.as_ref().map(|p| p.file_name().unwrap_or_default().to_string_lossy().to_string()).unwrap_or_else(|| "Untitled".into());
            ui.label(RichText::new(format!("{label}{}", if self.editor!=self.saved_text { " • unsaved" } else { "" })).weak());
        }));
        if self.confirm_clear {
            let mut action=0;
            egui::Window::new("Clear editor?").collapsible(false).resizable(false).anchor(egui::Align2::CENTER_CENTER,[0.0,0.0]).show(ui.ctx(),|ui| {
                ui.label("The editor has a file or unsaved changes. Clear it anyway?");
                ui.horizontal(|ui| { if ui.button("Cancel").clicked(){action=1;} if ui.button("Clear anyway").clicked(){action=2;} });
            });
            if action==1 { self.confirm_clear=false; }
            if action==2 { self.confirm_clear=false; self.clear_editor(); }
        }
        if self.confirm_open {
            let mut action=0;
            egui::Window::new("Unsaved editor changes").collapsible(false).resizable(false).anchor(egui::Align2::CENTER_CENTER,[0.0,0.0]).show(ui.ctx(),|ui| {
                ui.label("Save the current document before opening another file?");
                ui.horizontal(|ui| { if ui.button("Cancel").clicked(){action=1;} if ui.button("Discard").clicked(){action=2;} if ui.button("Save and open").clicked(){action=3;} });
            });
            match action {
                1=>{self.confirm_open=false;self.pending_open=None;},
                2=>{self.confirm_open=false;if let Some(path)=self.pending_open.take(){self.load_editor(path);}},
                3=>if self.save_editor(false){self.confirm_open=false;if let Some(path)=self.pending_open.take(){self.load_editor(path);}},
                _=>{}
            }
        }
        ui.add_space(4.0);
        if !self.plain_text {
            ui.horizontal_wrapped(|ui| {
                for (label, kind) in [("B","bold"),("I","italic"),("S","strike"),("H1","h1"),("H2","h2"),("H3","h3"),("H4","h4"),("H5","h5"),("H6","h6"),("• List","bullet"),("1. List","number"),("☑ Task","task"),("> Quote","quote"),("` Code","inline"),("{} Block","codeblock"),("Link","link"),("― Rule","rule")] {
                    if ui.small_button(label).on_hover_text(kind).clicked() { self.transform_editor(kind); }
                }
            });
        }
        ui.add_space(4.0);
        let changed_before = self.editor.clone();
        let selection_before = self.selection;
        let enter_pressed=ui.input(|i|i.key_pressed(egui::Key::Enter)&&!i.modifiers.shift&&!i.modifiers.ctrl&&!i.modifiers.command);
        let editor_area_height=(ui.available_height()-50.0).max(180.0);
        let editor_rows=(editor_area_height/18.0).floor().max(8.0) as usize;
        let mut output = if self.preview {
            let mut result=None;
            let total_width=ui.available_width();
            let pane_height=editor_area_height;
            let divider_width=10.0;
            let panes_width=(total_width-divider_width).max(100.0);
            let editor_width=(panes_width*self.preview_split).clamp(panes_width*0.25,panes_width*0.75);
            let parent_left=ui.max_rect().left();
            ui.horizontal_top(|ui| {
                ui.allocate_ui_with_layout(egui::vec2(editor_width,pane_height),egui::Layout::top_down(egui::Align::Min),|ui| {
                    result=Some(egui::ScrollArea::vertical().id_salt("source-editor-scroll").auto_shrink([false,false]).max_height(pane_height).show(ui,|ui| {
                        egui::TextEdit::multiline(&mut self.editor).id(self.editor_id).font(egui::TextStyle::Monospace).desired_width(f32::INFINITY).desired_rows(editor_rows).lock_focus(true).show(ui)
                    }).inner);
                });
                let (divider,response)=ui.allocate_exact_size(egui::vec2(divider_width,pane_height),egui::Sense::drag());
                if response.hovered()||response.dragged(){ui.ctx().set_cursor_icon(egui::CursorIcon::ResizeHorizontal);}
                if response.dragged(){
                    if let Some(pointer)=response.interact_pointer_pos(){self.preview_split=((pointer.x-parent_left-divider_width*0.5)/panes_width).clamp(0.25,0.75);}
                }
                let color=if response.hovered()||response.dragged(){ui.visuals().selection.bg_fill}else{ui.visuals().widgets.noninteractive.bg_stroke.color};
                ui.painter().line_segment([divider.center_top(),divider.center_bottom()],egui::Stroke::new(2.0,color));
                ui.allocate_ui_with_layout(egui::vec2((panes_width-editor_width).max(100.0),pane_height),egui::Layout::top_down(egui::Align::Min),|ui| {
                    egui::ScrollArea::vertical().auto_shrink([false,false]).show(ui,|ui|self.markdown_preview(ui));
                });
            });
            result.expect("editor column always produces a response")
        } else { egui::ScrollArea::vertical().id_salt("source-editor-scroll").auto_shrink([false,false]).max_height(editor_area_height).show(ui,|ui| {
            egui::TextEdit::multiline(&mut self.editor).id(self.editor_id).font(egui::TextStyle::Monospace).desired_width(f32::INFINITY).desired_rows(editor_rows).lock_focus(true).show(ui)
        }).inner };
        if output.response.has_focus()&&enter_pressed&&self.editor!=changed_before {
            if let Some((text,selection))=editor::continue_markdown_line(&changed_before,selection_before) {
                self.editor=text;
                self.selection=selection;
                self.pending_cursor_restore=true;
            }
        }
        let selection=self.selection;
        let has_selection=selection.0!=selection.1;
        let mut context_action=None;
        output.response.context_menu(|ui| {
            if ui.add_enabled(self.history.can_undo(),egui::Button::new("Undo")).clicked(){context_action=Some("undo");ui.close();}
            if ui.add_enabled(self.history.can_redo(),egui::Button::new("Redo")).clicked(){context_action=Some("redo");ui.close();}
            ui.separator();
            if ui.add_enabled(has_selection,egui::Button::new("Cut")).clicked(){context_action=Some("cut");ui.close();}
            if ui.add_enabled(has_selection,egui::Button::new("Copy")).clicked(){context_action=Some("copy");ui.close();}
            if ui.button("Paste").clicked(){context_action=Some("paste");ui.close();}
            ui.separator();
            if ui.button("Select all").clicked(){context_action=Some("select_all");ui.close();}
        });
        if let Some(action)=context_action {
            let (start,end)=(selection.0.min(selection.1).min(self.editor.len()),selection.0.max(selection.1).min(self.editor.len()));
            match action {
                "undo"=>self.undo(),
                "redo"=>self.redo(),
                "copy"=>ui.ctx().copy_text(self.editor[start..end].to_owned()),
                "cut"=>{ui.ctx().copy_text(self.editor[start..end].to_owned());self.editor.replace_range(start..end,"");self.selection=(start,start);self.pending_cursor_restore=true;},
                "paste"=>if let Ok(mut clipboard)=arboard::Clipboard::new(){if let Ok(text)=clipboard.get_text(){self.editor.replace_range(start..end,&text);let cursor=start+text.len();self.selection=(cursor,cursor);self.pending_cursor_restore=true;}},
                "select_all"=>{self.selection=(0,self.editor.len());self.pending_cursor_restore=true;},
                _=>{}
            }
        }
        self.editor_focused=output.response.has_focus();
        if self.focus_editor_on_start { output.response.request_focus(); self.focus_editor_on_start=false; self.pending_cursor_restore=true; }
        // A secondary click normally moves the text cursor to the click point.
        // When the user right-clicks inside an existing selection, keep that
        // selection so the context menu acts on the selected text.
        if output.response.secondary_clicked() && has_selection { self.pending_cursor_restore=true; }
        if !self.pending_cursor_restore { if let Some(range) = output.cursor_range.clone() {
            let chars = range.as_sorted_char_range();
            let byte_at = |n: usize, value: &str| value.char_indices().nth(n).map_or(value.len(), |(i,_)| i);
            self.selection = (byte_at(chars.start.0, &self.editor), byte_at(chars.end.0, &self.editor));
        } }
        if self.pending_cursor_restore {
            let byte_to_char=|index:usize,value:&str| value[..index.min(value.len())].chars().count();
            let start=byte_to_char(self.selection.0,&self.editor); let end=byte_to_char(self.selection.1,&self.editor);
            output.state.cursor.set_char_range(Some(egui::text::CCursorRange::two(egui::text::CCursor::new(start),egui::text::CCursor::new(end))));
            output.state.store(ui.ctx(),output.response.id);
            self.pending_cursor_restore=false;
        }
        if self.editor != changed_before {
            self.history.record(Snapshot { text: changed_before, selection: selection_before }, &self.editor_snapshot());
        }
        self.previous_text=self.editor.clone();
        ui.horizontal(|ui| {
            if ui.add_enabled(!self.editor.trim().is_empty() && !self.busy, primary_button("Create PDF")).clicked() {
                self.export_editor();
            }
            if ui.add_enabled(!self.editor.trim().is_empty() && !self.busy,egui::Button::new("Save PDF to…")).clicked() {
                if let Some(path)=rfd::FileDialog::new().add_filter("PDF", &["pdf"]).save_file() {
                    self.settings.output_directory=path.parent().unwrap_or(&path).to_string_lossy().into_owned();
                    self.settings.output_name=path.file_stem().unwrap_or_default().to_string_lossy().into_owned();
                    self.export_editor();
                }
            }
            if let Some(path)=self.last_results.iter().rev().find_map(|result|result.output.as_ref()) {
                if ui.add_enabled(path.is_file(),egui::Button::new("Open latest PDF")).clicked() {
                    if let Err(error)=open::that(path) { self.push_log(format!("[ERROR] Could not open PDF: {error}")); }
                }
            }
            ui.label(&self.status);
        });
    }

    fn documents_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Documents"); ui.label("Select one or more source documents to convert to PDF.");
        ui.horizontal(|ui| {
            if ui.button("Add files…").clicked() { self.add_files(); }
            if ui.button("Add folder…").clicked() {
                if let Some(dir)=rfd::FileDialog::new().pick_folder() {
                    if let Ok(items)=fs::read_dir(dir) {
                        let mut paths=items.flatten().map(|entry|entry.path())
                            .filter(|path|path.is_file()&&path.extension().and_then(|ext|ext.to_str())
                                .is_some_and(|ext|SUPPORTED_EXTENSIONS.contains(&ext.to_ascii_lowercase().as_str())))
                            .collect::<Vec<_>>();
                        paths.sort();
                        for path in paths { if !self.selected_files.contains(&path){self.selected_files.push(path);} }
                    }
                }
            }
            if ui.button("Remove all").clicked() { self.selected_files.clear(); }
        });
        let examples=config::input_dir();
        if let Ok(entries)=fs::read_dir(&examples) {
            let samples=entries.flatten().map(|e|e.path()).filter(|p|p.is_file()&&p.extension().and_then(|x|x.to_str()).is_some_and(|x|SUPPORTED_EXTENSIONS.contains(&x.to_lowercase().as_str()))).collect::<Vec<_>>();
            if !samples.is_empty() { ui.label("Quick samples"); ui.horizontal_wrapped(|ui|for path in samples { let name=path.file_name().unwrap_or_default().to_string_lossy(); if ui.small_button(name.as_ref()).clicked()&&!self.selected_files.contains(&path){self.selected_files.push(path);} }); }
        }
        ui.horizontal(|ui| { ui.label("Filter"); ui.text_edit_singleline(&mut self.input_filter); });
        egui::ScrollArea::vertical().max_height(220.0).show(ui, |ui| {
            let filter=self.input_filter.to_lowercase();
            let mut remove=Vec::new();
            for (i,path) in self.selected_files.iter().enumerate() {
                if !filter.is_empty() && !path.to_string_lossy().to_lowercase().contains(&filter) { continue; }
                ui.horizontal(|ui| { ui.label(path.file_name().unwrap_or_default().to_string_lossy()); ui.weak(path.parent().unwrap_or(path).to_string_lossy()); if ui.small_button("×").clicked(){remove.push(i);} });
            }
            for i in remove.into_iter().rev() { self.selected_files.remove(i); }
        });
        ui.separator(); self.output_settings(ui);
        ui.horizontal(|ui| {
            if ui.add_enabled(!self.selected_files.is_empty() && !self.busy, primary_button("Convert selected to PDF")).clicked() { self.start_conversion(self.selected_files.clone(), None, None, Vec::new()); }
            if ui.button("Open output folder").clicked() { let _=open::that(&self.settings.output_directory); }
            if !self.last_results.is_empty() { if ui.button("Open latest PDF").clicked() { if let Some(path)=self.last_results.iter().find_map(|r|r.output.as_ref()){ let _=open::that(path); } } }
        });
        ui.horizontal(|ui| {
            let changed=ui.checkbox(&mut self.auto_watch,"Auto-Convert (Watch)").changed();
            if changed {
                if self.auto_watch {
                    if self.selected_files.len()==1 && self.selected_files[0].is_file() {
                        let path=self.selected_files[0].clone();
                        self.watched_modified=fs::metadata(&path).and_then(|m|m.modified()).ok();
                        self.watched_path=Some(path.clone());
                        self.last_watch_convert=SystemTime::now();
                        self.push_log(format!("[WATCH] Auto-convert started on '{}'.",path.file_name().unwrap_or_default().to_string_lossy()));
                        self.start_conversion(vec![path],None,None,Vec::new());
                    } else {
                        self.auto_watch=false;
                        self.push_log("[ERROR] Auto-convert requires exactly one valid document.");
                    }
                } else {
                    self.watched_path=None;
                    self.push_log("[WATCH] Auto-convert stopped.");
                }
            }
            if self.auto_watch { ui.weak("The selected file is watched while this window is open."); }
        });
    }

    fn output_settings(&mut self, ui: &mut egui::Ui) {
        egui::CollapsingHeader::new("Output name and destination").default_open(true).show(ui, |ui| {
            egui::Grid::new("output-grid").num_columns(2).show(ui, |ui| {
                ui.label("Output name"); ui.text_edit_singleline(&mut self.settings.output_name); ui.end_row();
                ui.label("Output folder"); ui.horizontal(|ui| { ui.text_edit_singleline(&mut self.settings.output_directory); if ui.button("Browse…").clicked(){ if let Some(p)=rfd::FileDialog::new().pick_folder(){self.settings.output_directory=p.to_string_lossy().into_owned();} } }); ui.end_row();
            });
        });
    }

    fn page_layout_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Page and Geometry"); ui.label("Paper dimensions, orientation, margins, and page decoration.");
        egui::Grid::new("page-settings").num_columns(2).spacing([14.0,8.0]).show(ui, |ui| {
            ui.label("Paper Size"); combo(ui,"page-size",&mut self.settings.page_size_choice,&["A4","Letter","A5","Legal","For Mobile","For PC"]); ui.end_row();
            ui.label("Orientation"); combo(ui,"orientation",&mut self.settings.orientation,&["Portrait","Landscape"]); ui.end_row();
            ui.label("Margin Preset"); combo(ui,"margin",&mut self.settings.margin_choice,&["Page default","Narrow (0.5 in)","Standard (1 in)","Wide (1.25 in)","Wide (1.5 in)","Compact (7 mm)","Custom"]); ui.end_row();
            if self.settings.margin_choice=="Custom" { ui.label("Custom Margin"); ui.text_edit_singleline(&mut self.settings.custom_margin); ui.end_row(); }
            ui.label("Decorative Page Border"); ui.checkbox(&mut self.settings.page_border,""); ui.end_row();
        }); self.output_settings(ui);
    }

    fn typography_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Typography"); ui.label("Font choices are bundled with the app where licensed and available.");
        egui::Grid::new("font-settings").num_columns(2).spacing([14.0,8.0]).show(ui, |ui| {
            ui.label("English Font"); font_combo(ui,"english",&mut self.settings.english_font,ENGLISH_FONTS,&mut self.font_search[0]); ui.end_row();
            ui.label("Heading Font"); font_combo(ui,"heading",&mut self.settings.heading_font,HEADING_FONTS,&mut self.font_search[1]); ui.end_row();
            ui.label("Bengali Font"); font_combo(ui,"bengali",&mut self.settings.bengali_font,BENGALI_FONTS,&mut self.font_search[2]); ui.end_row();
            ui.label("Arabic Font"); font_combo(ui,"arabic",&mut self.settings.arabic_font,ARABIC_FONTS,&mut self.font_search[3]); ui.end_row();
            ui.label("Coding / Monospace Font"); font_combo(ui,"code",&mut self.settings.code_font,CODE_FONTS,&mut self.font_search[4]); ui.end_row();
            ui.label("Font Size Preset"); combo(ui,"font-size",&mut self.settings.font_size_choice,&["Standard","Medium","Large","Custom"]); ui.end_row();
            if self.settings.font_size_choice=="Custom" { ui.label("Custom Font Size (pt)"); ui.add(egui::DragValue::new(&mut self.settings.custom_font_size).range(6.0..=72.0)); ui.end_row(); }
            ui.label("Line Spacing Multiplier"); combo(ui,"line-height",&mut self.settings.line_height,&["1.0","1.1","1.15","1.2","1.25","1.5"]); ui.end_row();
            ui.label("Paragraph Spacing"); combo(ui,"paragraph-spacing",&mut self.settings.paragraph_spacing,&["0pt","3pt","6pt","9pt","12pt"]); ui.end_row();
            ui.label("Bold Headings"); ui.checkbox(&mut self.settings.bold_headings,""); ui.end_row();
            ui.label("Center Headings"); ui.checkbox(&mut self.settings.center_headings,""); ui.end_row();
            ui.label("Hyphenation"); ui.checkbox(&mut self.settings.hyphenation,""); ui.end_row();
            ui.label("First Line Indent"); ui.checkbox(&mut self.settings.indent_first_line,""); ui.end_row();
            if self.settings.indent_first_line { ui.label("Indent Amount"); ui.text_edit_singleline(&mut self.settings.indent_amount); ui.end_row(); }
            ui.label("Copy-friendly text"); ui.checkbox(&mut self.settings.copy_friendly_text,""); ui.end_row();
        });
    }

    fn toc_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("TOC and Page Numbers");
        egui::Grid::new("toc-settings").num_columns(2).spacing([14.0,8.0]).show(ui, |ui| {
            ui.label("Include Table of Contents"); ui.checkbox(&mut self.settings.include_toc,""); ui.end_row();
            ui.label("Beautify TOC"); ui.checkbox(&mut self.settings.beautify_toc,""); ui.end_row();
            ui.label("TOC Language"); combo(ui,"toc-language",&mut self.settings.toc_language,&["English","Bangla"]); ui.end_row();
            ui.label("TOC Title Alignment"); combo(ui,"toc-align",&mut self.settings.toc_alignment,&["Left","Center","Right"]); ui.end_row();
            ui.label("TOC Design"); combo(ui,"toc-design",&mut self.settings.toc_design,&["Classic","Minimal","Decorative"]); ui.end_row();
            ui.label("Page Numbers"); ui.checkbox(&mut self.settings.page_numbers,""); ui.end_row();
            if self.settings.page_numbers { ui.label("Position"); combo(ui,"page-number-position",&mut self.settings.page_number_position,&["Bottom left","Middle","Bottom right"]); ui.end_row();
                ui.label("Format"); combo(ui,"page-number-format",&mut self.settings.page_number_format,&["Page 1 of 10","1 / 10","Page 1","1"]); ui.end_row();
                ui.label("Numeral Language"); combo(ui,"page-number-language",&mut self.settings.page_number_language,&["English","Bangla"]); ui.end_row();
                ui.label("Numbering Style"); combo(ui,"number-style",&mut self.settings.page_number_style,&["arabic","roman"]); ui.end_row(); }
            ui.label("Front matter page numbers"); ui.checkbox(&mut self.settings.front_page_numbers,""); ui.end_row();
            if self.settings.front_page_numbers { ui.label("Front matter style"); combo(ui,"front-style",&mut self.settings.front_page_number_style,&["roman","arabic"]); ui.end_row();
                ui.label("Front matter format"); combo(ui,"front-format",&mut self.settings.front_page_number_format,&["Page 1 of 10","1 / 10","Page 1","1"]); ui.end_row();
                ui.label("Position"); combo(ui,"front-position",&mut self.settings.front_page_number_position,&["Bottom left","Middle","Bottom right"]); ui.end_row();
                ui.label("Numeral Language"); combo(ui,"front-language",&mut self.settings.front_page_number_language,&["English","Bangla"]); ui.end_row(); }
        });
    }

    fn profiles_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Configuration Profiles");
        let builtins=["Mobile","PC","English","Bangla"];
        let mut names=Vec::new();
        for name in &builtins { if self.profiles.contains_key(*name) { names.push((*name).to_owned()); } }
        for name in self.profiles.keys() { if !builtins.contains(&name.as_str()) { names.push(name.clone()); } }
        egui::ComboBox::from_label("Choose Profile Preset").selected_text(&self.profile_name).show_ui(ui,|ui| {
            for name in &names { ui.selectable_value(&mut self.profile_name,name.clone(),name); }
        });
        ui.horizontal_wrapped(|ui| {
            if ui.button("Load profile").clicked(){
                if let Some(settings)=self.profiles.get(&self.profile_name).cloned(){
                    self.settings=settings;
                    self.dark=match self.settings.theme_mode.as_str(){"light"=>false,"dark"=>true,_=>system_theme_is_dark()};
                    self.settings.highlight_style="tango".into();
                    apply_visual_style(ui.ctx(),self.dark);
                }
            }
            if ui.button("Update profile").clicked(){ match profiles::update_profile(&self.profile_name,&self.settings){Ok(())=>{self.profiles.insert(self.profile_name.clone(),self.settings.clone());self.save_last_settings();self.push_log("[PROFILE] Updated profile.");},Err(e)=>self.push_log(format!("[ERROR] {e}"))} }
            if ui.button("Delete profile").clicked(){ match profiles::delete_profile(&self.profile_name){Ok(())=>{self.profiles.remove(&self.profile_name);self.profile_name="PC".into();self.push_log("[PROFILE] Deleted profile.");},Err(e)=>self.push_log(format!("[ERROR] {e}"))} }
        });
        ui.separator(); ui.label("Save Current Configuration");
        ui.horizontal(|ui| { ui.text_edit_singleline(&mut self.new_profile_name); if ui.button("Save as New").clicked(){let name=self.new_profile_name.trim().to_owned();match profiles::save_profile(&name,&self.settings){Ok(())=>{self.profiles.insert(name.clone(),self.settings.clone());self.profile_name=name;self.new_profile_name.clear();self.push_log("[PROFILE] Saved new profile.");},Err(e)=>self.push_log(format!("[ERROR] {e}"))}} });
        ui.weak(format!("{} profile(s) available",self.profiles.len()));
    }

    fn help_view(&mut self, ui: &mut egui::Ui) {
        ui.heading("Help"); ui.horizontal(|ui| { ui.label("Search topics"); ui.text_edit_singleline(&mut self.help_search); });
        const GUIDE: &str = include_str!("../docs/USER_GUIDE.md");
        let query=self.help_search.to_lowercase();
        let topics=GUIDE.lines().filter_map(|line| line.strip_prefix("## ")).filter(|title| query.is_empty() || format!("{title} {} {}",guide_section(GUIDE,title),guide_search_terms(title)).to_lowercase().contains(&query)).collect::<Vec<_>>();
        if !topics.iter().any(|topic| topic.eq_ignore_ascii_case(&self.help_selected)) {
            if let Some(topic)=topics.first() { self.help_selected=(*topic).to_owned(); }
        }
        ui.horizontal_top(|ui| {
            ui.vertical(|ui| { ui.set_width(230.0); if topics.is_empty(){ui.weak("No matching topics.");} for topic in &topics { if ui.selectable_label(self.help_selected==**topic,*topic).clicked(){self.help_selected=(**topic).to_string();} } });
            ui.separator(); egui::ScrollArea::vertical().show(ui,|ui| {
                if topics.is_empty() { ui.heading("No matching help topic"); }
                else {
                    let section=guide_section(GUIDE,&self.help_selected);
                    let viewer=egui_commonmark::CommonMarkViewer::new();
                    let viewer=if self.dark { viewer.syntax_theme_dark("base16-ocean.dark") } else { viewer.syntax_theme_light("InspiredGitHub") };
                    viewer.show(ui,&mut self.help_cache,&section);
                }
                ui.add_space(8.0);
                if ui.button("Open full user guide").clicked(){let _=open::that(config::resource_dir().join("docs/USER_GUIDE.md"));}
            });
        });
    }

    fn log_panel(&mut self, ui: &mut egui::Ui) {
        ui.separator();
        ui.horizontal(|ui| {
            if ui.selectable_label(self.log_expanded,"Conversion log").clicked(){self.log_expanded=!self.log_expanded;}
            ui.label(&self.status);
            if ui.button("Copy log").clicked(){ui.ctx().copy_text(self.log_lines.join("\n"));}
            if ui.button("Clear log").clicked(){self.log_lines.clear();}
        });
        if self.log_expanded {
            egui::ScrollArea::vertical().stick_to_bottom(true).max_height(150.0).show(ui,|ui| {
                let text=self.log_lines.join("\n");
                ui.add(egui::Label::new(RichText::new(text).monospace()).selectable(true).wrap());
            });
        }
    }

    fn save_last_settings(&mut self) {
        self.last_persist_attempt=Some(std::time::Instant::now());
        match profiles::save_last_used(&self.settings,&self.profile_name) {
            Ok(())=>{self.persisted_settings=self.settings.clone();self.persisted_profile_name=self.profile_name.clone();}
            Err(error)=>self.push_log(format!("[WARNING] Could not save preferences: {error}")),
        }
    }

    fn update_watch(&mut self) {
        if !self.auto_watch { self.watched_path=None; return; }
        if self.selected_files.len()!=1 || !self.selected_files[0].is_file() {
            self.auto_watch=false; self.watched_path=None;
            self.push_log("[WATCH] Auto-convert stopped because exactly one valid file must be selected.");
            return;
        }
        let path=self.selected_files[0].clone();
        let modified=fs::metadata(&path).and_then(|m|m.modified()).ok();
        if self.watched_path.as_ref()!=Some(&path) {
            self.watched_path=Some(path.clone()); self.watched_modified=modified; self.last_watch_convert=SystemTime::now();
            self.push_log(format!("[WATCH] Selection changed; watching '{}'.",path.display()));
            self.start_conversion(vec![path],None,None,Vec::new());
            return;
        }
        if modified.is_some() && modified!=self.watched_modified && self.last_watch_convert.elapsed().unwrap_or_default()>Duration::from_secs(2) && !self.busy {
            self.watched_modified=modified; self.last_watch_convert=SystemTime::now();
            self.push_log(format!("[WATCH] Change detected in '{}'.",path.display()));
            self.start_conversion(vec![path],None,None,Vec::new());
        }
    }
}

impl eframe::App for StudioApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx=ui.ctx().clone();
        // eframe creates the app's root Ui before `StudioApp::new` applies the
        // saved theme to the context. Refresh that Ui so first-frame panels
        // and widgets use the same visuals as nested widgets.
        ui.set_style(ctx.style_of(ctx.theme()));
        self.poll_worker();
        self.update_watch();
        if self.auto_watch { ctx.request_repaint_after(Duration::from_millis(800)); }
        if self.settings.theme_mode=="system" {
            let system_dark=system_theme_is_dark();
            if self.dark!=system_dark {
                self.dark=system_dark;
                self.settings.highlight_style="tango".into();
                apply_visual_style(&ctx,self.dark);
            }
            ctx.request_repaint_after(Duration::from_secs(2));
        }
        if self.view==View::Editor {
            if let Some((key,modifiers,action))=editor_shortcut(&ctx) {
                ctx.input_mut(|i|{i.consume_key(modifiers,key);});
                match action {
                    EditorShortcut::Open=>self.open_editor(),
                    EditorShortcut::Save=>{self.save_editor(false);},
                    EditorShortcut::SaveAs=>{self.save_editor(true);},
                    EditorShortcut::New=>if self.editor_path.is_some()||self.editor!=self.saved_text {self.confirm_clear=true;}else{self.clear_editor();},
                    EditorShortcut::Undo=>self.undo(),
                    EditorShortcut::Redo=>self.redo(),
                    EditorShortcut::Bold=>self.transform_editor("bold"),
                    EditorShortcut::Italic=>self.transform_editor("italic"),
                    EditorShortcut::Strike=>self.transform_editor("strike"),
                    EditorShortcut::Link=>self.transform_editor("link"),
                    EditorShortcut::CodeBlock=>self.transform_editor("codeblock"),
                    EditorShortcut::Export=>self.export_editor(),
                }
            }
        }
        egui::Panel::top("top-bar").frame(egui::Frame::new().fill(ui.visuals().panel_fill).inner_margin(egui::Margin::symmetric(18, 10))).show(ui,|ui|self.top_bar(ui));
        egui::Panel::bottom("log-panel").resizable(true).default_size(170.0).frame(egui::Frame::new().fill(ui.visuals().panel_fill).inner_margin(egui::Margin::symmetric(14, 8))).show(ui,|ui|self.log_panel(ui));
        egui::Panel::left("navigation").resizable(false).exact_size(220.0).frame(egui::Frame::new().fill(ui.visuals().panel_fill).inner_margin(egui::Margin::same(14))).show(ui,|ui|self.side_nav(ui));
        self.editor_focused=false;
        let canvas=if self.dark { egui::Color32::from_rgb(16,23,33) } else { egui::Color32::from_rgb(244,247,251) };
        egui::CentralPanel::default().frame(egui::Frame::new().fill(canvas).inner_margin(egui::Margin::same(22))).show(ui,|ui| {
            match self.view {
                View::Editor=>self.editor_view(ui),
                view=>{ egui::ScrollArea::vertical().show(ui,|ui|match view {
                    View::Documents=>self.documents_view(ui), View::PageLayout=>self.page_layout_view(ui),
                    View::Typography=>self.typography_view(ui), View::Toc=>self.toc_view(ui),
                    View::Profiles=>self.profiles_view(ui), View::Help=>self.help_view(ui), View::Editor=>unreachable!(),
                }); }
            }
        });
        if ctx.input(|i|i.viewport().close_requested()) {
            if self.editor!=self.saved_text {
                ctx.send_viewport_cmd(egui::ViewportCommand::CancelClose);
                self.confirm_close=true;
            } else { self.save_last_settings(); }
        }
        if self.confirm_close {
            let mut action=0;
            egui::Window::new("Unsaved editor changes").collapsible(false).resizable(false).anchor(egui::Align2::CENTER_CENTER,[0.0,0.0]).show(&ctx,|ui| {
                ui.label("Save your editor changes before closing?");
                ui.horizontal(|ui| { if ui.button("Cancel").clicked(){action=1;} if ui.button("Discard and close").clicked(){action=2;} if ui.button("Save and close").clicked(){action=3;} });
            });
            match action {
                1=>self.confirm_close=false,
                2=>{self.confirm_close=false;self.saved_text=self.editor.clone();self.save_last_settings();ctx.send_viewport_cmd(egui::ViewportCommand::Close);},
                3=>if self.save_editor(false){self.confirm_close=false;self.save_last_settings();ctx.send_viewport_cmd(egui::ViewportCommand::Close);},
                _=>{}
            }
        }
        let preferences_changed=self.settings!=self.persisted_settings||self.profile_name!=self.persisted_profile_name;
        let retry_allowed=self.last_persist_attempt.is_none_or(|attempt|attempt.elapsed()>=Duration::from_secs(2));
        if preferences_changed&&retry_allowed {
            self.save_last_settings();
        }
    }
}

#[derive(Clone, Copy)]
enum EditorShortcut { Open, Save, SaveAs, New, Undo, Redo, Bold, Italic, Strike, Link, CodeBlock, Export }

fn editor_shortcut(ctx:&egui::Context)->Option<(egui::Key,egui::Modifiers,EditorShortcut)> {
    ctx.input(|input| {
        let modifiers=input.modifiers;
        if !modifiers.command||modifiers.alt { return None; }
        let bindings=[
            (egui::Key::O,false,EditorShortcut::Open),
            (egui::Key::S,false,EditorShortcut::Save),
            (egui::Key::S,true,EditorShortcut::SaveAs),
            (egui::Key::N,false,EditorShortcut::New),
            (egui::Key::Z,false,EditorShortcut::Undo),
            (egui::Key::Z,true,EditorShortcut::Redo),
            (egui::Key::Y,false,EditorShortcut::Redo),
            (egui::Key::B,false,EditorShortcut::Bold),
            (egui::Key::I,false,EditorShortcut::Italic),
            (egui::Key::X,true,EditorShortcut::Strike),
            (egui::Key::K,false,EditorShortcut::Link),
            (egui::Key::C,true,EditorShortcut::CodeBlock),
            (egui::Key::Enter,false,EditorShortcut::Export),
        ];
        bindings.into_iter().find(|(key,shift,_)|modifiers.shift==*shift&&input.key_pressed(*key))
            .map(|(key,_,action)|(key,modifiers,action))
    })
}

fn combo(ui: &mut egui::Ui, id: &str, value: &mut String, choices: &[&str]) {
    egui::ComboBox::from_id_salt(id).selected_text(value.as_str()).show_ui(ui,|ui|for choice in choices { ui.selectable_value(value,(*choice).to_string(),*choice); });
}

fn primary_button(label:&str)->egui::Button<'_> {
    egui::Button::new(RichText::new(label).strong().color(egui::Color32::WHITE))
        .fill(egui::Color32::from_rgb(24,164,156))
        .stroke(egui::Stroke::new(1.0,egui::Color32::from_rgb(24,164,156)))
        .corner_radius(egui::CornerRadius::same(7))
}

fn nav_button(ui:&mut egui::Ui,selected:bool,glyph:&str,fallback:&str,label:&str)->bool {
    let (rect,response)=ui.allocate_exact_size(egui::vec2(ui.available_width(),38.0),egui::Sense::click());
    let visuals=ui.visuals();
    let background=if selected { visuals.selection.bg_fill } else if response.hovered() { visuals.widgets.hovered.weak_bg_fill } else { egui::Color32::TRANSPARENT };
    if background!=egui::Color32::TRANSPARENT { ui.painter().rect_filled(rect,egui::CornerRadius::same(7),background); }
    let foreground=if selected { if visuals.dark_mode { egui::Color32::from_rgb(134,233,222) } else { egui::Color32::from_rgb(0,103,101) } } else { visuals.text_color() };
    let center=rect.left_center()+egui::vec2(20.0,0.0);
    #[cfg(windows)]
    ui.painter().text(center,egui::Align2::CENTER_CENTER,glyph,egui::FontId::new(17.0,egui::FontFamily::Name("Segoe MDL2 Assets".into())),foreground);
    #[cfg(not(windows))]
    ui.painter().text(center,egui::Align2::CENTER_CENTER,fallback,egui::FontId::new(9.0,egui::FontFamily::Proportional),foreground);
    ui.painter().text(rect.left_center()+egui::vec2(42.0,0.0),egui::Align2::LEFT_CENTER,label,egui::FontId::new(13.5,egui::FontFamily::Proportional),foreground);
    response.clicked()
}

fn font_combo(ui: &mut egui::Ui,id:&str,value:&mut String,choices:&[&str],search:&mut String) {
    let popup_id=ui.make_persistent_id(id).with("popup");
    egui::ComboBox::from_id_salt(id).selected_text(value.as_str()).close_behavior(egui::PopupCloseBehavior::CloseOnClickOutside).show_ui(ui,|ui| {
        ui.text_edit_singleline(search);
        let query=search.to_lowercase();
        for choice in choices.iter().filter(|name|query.is_empty()||name.to_lowercase().contains(&query)) { if ui.selectable_value(value,(*choice).to_string(),*choice).clicked(){search.clear();egui::Popup::close_id(ui.ctx(),popup_id);} }
        let system=installed_font_families().iter()
            .filter(|name|!choices.iter().any(|choice|choice.eq_ignore_ascii_case(name.as_str()))
                &&(query.is_empty()||name.to_lowercase().contains(&query)));
        let mut has_system_font=false;
        for family in system {
            if !has_system_font { ui.separator(); has_system_font=true; }
            if ui.selectable_value(value,family.as_str().to_owned(),family.as_str()).clicked(){search.clear();egui::Popup::close_id(ui.ctx(),popup_id);}
        }
    });
}

fn guide_section(guide:&str,title:&str)->String {
    let mut active=false;let mut lines=Vec::new();
    for line in guide.lines() {
        if let Some(next)=line.strip_prefix("## ") { if active { break; } active=next==title; }
        if active { lines.push(line); }
    }
    if lines.is_empty() { format!("## {title}\n\nNo matching help topic was found.") } else { lines.join("\n") }
}

fn guide_search_terms(title:&str)->&'static str {
    match title {
        "Getting Started" => "first launch conversion workflow start install setup launch convert quick start",
        "Document Editor" => "open edit save save as clear close new file buffer markdown plain text",
        "Editor Preview and Resizing" => "preview live markdown split resize expand drag divider fullscreen maximize",
        "Markdown Formatting" => "markdown syntax bold italic heading list quote code link rule toolbar format",
        "Help and Search" => "help search topics find guide user guide documentation",
        "Keyboard Shortcuts" => "keyboard shortcut hotkey ctrl command open save new undo redo bold italic strike link code pdf enter",
        "Page and Geometry" => "page size paper a4 letter a5 legal orientation portrait landscape margin border",
        "Typography" => "font typography size bengali arabic english heading line spacing indent bold headings hyphenation",
        "TOC and Page Numbers" => "toc table of contents page numbers language design beautify alignment numeral",
        "Auto-Convert Watch Mode" => "watch auto convert monitor reload mode continuous recompile changes",
        "Configuration Profiles" => "profile configuration save apply update delete settings preset",
        "Documents and Conversion" => "batch add file folder output filename destination document formats conversion log",
        "CLI" => "command line terminal headless ssh wizard arguments watch interval batch profile",
        "Troubleshooting" => "error pandoc xelatex latex missing install fails debug problem log",
        _ => "",
    }
}

fn apply_system_font(ctx:&egui::Context) {
    #[cfg(windows)] {
        let candidates=[r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeui Variable.ttf"];
        if let Some(bytes)=candidates.iter().find_map(|path|fs::read(path).ok()) {
            let mut fonts=egui::FontDefinitions::default();
            fonts.font_data.insert("Segoe UI".into(),std::sync::Arc::new(egui::FontData::from_owned(bytes)));
            fonts.families.entry(egui::FontFamily::Proportional).or_default().insert(0,"Segoe UI".into());
            if let Ok(icons)=fs::read(r"C:\Windows\Fonts\segmdl2.ttf") {
                fonts.font_data.insert("Segoe MDL2 Assets".into(),std::sync::Arc::new(egui::FontData::from_owned(icons)));
                fonts.families.insert(egui::FontFamily::Name("Segoe MDL2 Assets".into()),vec!["Segoe MDL2 Assets".into()]);
            }
            ctx.set_fonts(fonts);
        }
    }
}

fn apply_visual_style(ctx:&egui::Context,dark:bool) {
    let accent=egui::Color32::from_rgb(24,164,156);
    let mut visuals=if dark { egui::Visuals::dark() } else { egui::Visuals::light() };
    visuals.dark_mode=dark;
    visuals.panel_fill=if dark { egui::Color32::from_rgb(24,32,44) } else { egui::Color32::from_rgb(255,255,255) };
    visuals.window_fill=if dark { egui::Color32::from_rgb(25,34,47) } else { egui::Color32::from_rgb(255,255,255) };
    visuals.extreme_bg_color=if dark { egui::Color32::from_rgb(16,23,33) } else { egui::Color32::from_rgb(248,250,253) };
    visuals.text_edit_bg_color=Some(if dark { egui::Color32::from_rgb(18,26,37) } else { egui::Color32::from_rgb(255,255,255) });
    visuals.code_bg_color=if dark { egui::Color32::from_rgb(20,29,41) } else { egui::Color32::from_rgb(239,244,249) };
    visuals.faint_bg_color=if dark { egui::Color32::from_rgb(31,42,57) } else { egui::Color32::from_rgb(242,246,250) };
    visuals.hyperlink_color=if dark { egui::Color32::from_rgb(102,204,220) } else { egui::Color32::from_rgb(0,111,135) };
    visuals.selection.bg_fill=if dark { egui::Color32::from_rgb(29,104,109) } else { egui::Color32::from_rgb(190,235,229) };
    visuals.selection.stroke=egui::Stroke::new(1.0,accent);
    visuals.window_corner_radius=egui::CornerRadius::same(10);
    visuals.menu_corner_radius=egui::CornerRadius::same(8);
    let border=if dark { egui::Color32::from_rgb(52,66,84) } else { egui::Color32::from_rgb(218,226,236) };
    let button=if dark { egui::Color32::from_rgb(35,47,63) } else { egui::Color32::from_rgb(247,249,252) };
    let hover=if dark { egui::Color32::from_rgb(43,62,79) } else { egui::Color32::from_rgb(232,242,247) };
    for widget in [&mut visuals.widgets.noninteractive,&mut visuals.widgets.inactive,&mut visuals.widgets.hovered,&mut visuals.widgets.active,&mut visuals.widgets.open] {
        widget.corner_radius=egui::CornerRadius::same(7);
        widget.bg_stroke=egui::Stroke::new(1.0,border);
    }
    visuals.widgets.inactive.bg_fill=button;
    visuals.widgets.inactive.weak_bg_fill=button;
    visuals.widgets.hovered.bg_fill=hover;
    visuals.widgets.hovered.weak_bg_fill=hover;
    visuals.widgets.active.bg_fill=if dark { egui::Color32::from_rgb(29,104,109) } else { egui::Color32::from_rgb(211,240,235) };
    visuals.widgets.active.weak_bg_fill=visuals.widgets.active.bg_fill;
    visuals.widgets.open.bg_fill=hover;
    visuals.widgets.open.weak_bg_fill=hover;
    visuals.widgets.noninteractive.fg_stroke.color=if dark { egui::Color32::from_rgb(218,227,238) } else { egui::Color32::from_rgb(39,51,66) };
    visuals.widgets.inactive.fg_stroke.color=visuals.widgets.noninteractive.fg_stroke.color;
    visuals.widgets.hovered.fg_stroke.color=visuals.widgets.noninteractive.fg_stroke.color;
    visuals.widgets.active.fg_stroke.color=if dark { egui::Color32::WHITE } else { egui::Color32::from_rgb(0,83,91) };
    visuals.widgets.open.fg_stroke.color=visuals.widgets.noninteractive.fg_stroke.color;
    ctx.set_visuals(visuals);
    ctx.all_styles_mut(|style| {
        style.spacing.item_spacing=egui::vec2(10.0,9.0);
        style.spacing.button_padding=egui::vec2(12.0,7.0);
        style.spacing.interact_size=egui::vec2(40.0,28.0);
        style.text_styles.insert(egui::TextStyle::Body,egui::FontId::new(14.0,egui::FontFamily::Proportional));
        style.text_styles.insert(egui::TextStyle::Button,egui::FontId::new(13.5,egui::FontFamily::Proportional));
        style.text_styles.insert(egui::TextStyle::Heading,egui::FontId::new(23.0,egui::FontFamily::Proportional));
        style.text_styles.insert(egui::TextStyle::Small,egui::FontId::new(11.5,egui::FontFamily::Proportional));
    });
}

fn system_theme_is_dark()->bool {
    #[cfg(windows)] {
        use winreg::{enums::HKEY_CURRENT_USER,RegKey};
        let key=RegKey::predef(HKEY_CURRENT_USER);
        return key.open_subkey("Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize")
            .and_then(|theme|theme.get_value::<u32,_>("AppsUseLightTheme"))
            .map(|light|light==0).unwrap_or(false);
    }
    #[cfg(target_os="macos")] {
        return std::process::Command::new("defaults").args(["read","-g","AppleInterfaceStyle"]).output()
            .is_ok_and(|output|output.status.success()&&String::from_utf8_lossy(&output.stdout).to_lowercase().contains("dark"));
    }
    #[cfg(all(unix,not(target_os="macos")))] {
        if let Ok(output)=std::process::Command::new("gsettings").args(["get","org.gnome.desktop.interface","color-scheme"]).output() {
            if output.status.success(){return String::from_utf8_lossy(&output.stdout).to_lowercase().contains("dark");}
        }
        return std::process::Command::new("gsettings").args(["get","org.gnome.desktop.interface","gtk-theme"]).output()
            .is_ok_and(|output|output.status.success()&&String::from_utf8_lossy(&output.stdout).to_lowercase().contains("dark"));
    }
    #[allow(unreachable_code)] false
}

fn installed_font_families()->&'static std::collections::BTreeSet<String> {
    static FONTS: std::sync::OnceLock<std::collections::BTreeSet<String>>=std::sync::OnceLock::new();
    FONTS.get_or_init(|| {
        #[cfg(windows)] {
            use winreg::{enums::{HKEY_CURRENT_USER,HKEY_LOCAL_MACHINE},RegKey};
            let mut fonts=std::collections::BTreeSet::new();
            let locations=[(HKEY_LOCAL_MACHINE,"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts"),(HKEY_CURRENT_USER,"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts")];
            for (hive,path) in locations { if let Ok(key)=RegKey::predef(hive).open_subkey(path) { for entry in key.enum_values().flatten() { let name=entry.0; let family=name.split('(').next().unwrap_or(&name).trim(); if !family.is_empty(){fonts.insert(family.to_owned());} } } }
            fonts
        }
        #[cfg(not(windows))] {
            std::process::Command::new("fc-list").args([":", "family"]).output().ok().filter(|o|o.status.success()).map(|o|String::from_utf8_lossy(&o.stdout).lines().flat_map(|line|line.split(',')).map(str::trim).filter(|s|!s.is_empty()).map(str::to_owned).collect::<std::collections::BTreeSet<_>>()).unwrap_or_default()
        }
    })
}

