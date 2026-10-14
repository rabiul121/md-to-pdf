use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, env, path::PathBuf};

pub const APP_NAME: &str = "PDF Creator Studio";
pub const SUPPORTED_EXTENSIONS: &[&str] = &["md", "markdown", "txt", "doc", "docx", "epub", "mobi"];

pub fn project_root() -> PathBuf {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest.parent().unwrap_or(&manifest).to_path_buf()
}

pub fn resource_dir() -> PathBuf {
    let beside_exe = std::env::current_exe().ok().and_then(|p| p.parent().map(PathBuf::from)).map(|p| p.join("resources"));
    if let Some(path) = beside_exe.filter(|p| p.join("src/template.tex").is_file()) { path } else { project_root() }
}

pub fn is_packaged() -> bool {
    resource_dir() != project_root()
}

pub fn data_dir() -> PathBuf {
    if is_packaged() { app_data_dir() } else { project_root() }
}

pub fn app_data_dir() -> PathBuf {
    #[cfg(windows)]
    if let Some(local) = env::var_os("LOCALAPPDATA").or_else(|| env::var_os("APPDATA")) {
        return PathBuf::from(local).join(APP_NAME);
    }
    #[cfg(target_os = "macos")]
    if let Some(home) = env::var_os("HOME") {
        return PathBuf::from(home).join("Library/Application Support").join(APP_NAME);
    }
    #[cfg(target_os = "linux")]
    {
        if let Some(xdg) = env::var_os("XDG_DATA_HOME") {
            return PathBuf::from(xdg).join(APP_NAME);
        }
        if let Some(home) = env::var_os("HOME") {
            return PathBuf::from(home).join(".local/share").join(APP_NAME);
        }
    }
    project_root()
}

pub fn output_dir() -> PathBuf {
    if !is_packaged() { return project_root().join("output"); }
    if let Some(home) = env::var_os("USERPROFILE").or_else(|| env::var_os("HOME")) {
        PathBuf::from(home).join("Documents").join("Markdown to PDF")
    } else {
        project_root().join("output")
    }
}

pub fn input_dir() -> PathBuf {
    if is_packaged() {
        std::env::current_exe().ok().and_then(|p| p.parent().map(PathBuf::from))
            .map(|p| p.join("input")).unwrap_or_else(|| project_root().join("input"))
    } else {
        project_root().join("input")
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Settings {
    pub theme_mode: String,
    pub highlight_style: String,
    pub page_size_choice: String,
    pub orientation: String,
    pub margin_choice: String,
    pub custom_margin: String,
    pub font_size_choice: String,
    pub custom_font_size: f32,
    pub english_font: String,
    pub heading_font: String,
    pub bengali_font: String,
    pub arabic_font: String,
    pub code_font: String,
    pub page_numbers: bool,
    pub page_number_style: String,
    pub page_number_format: String,
    pub page_number_position: String,
    pub page_number_size: String,
    pub page_number_language: String,
    pub front_page_numbers: bool,
    pub front_page_number_style: String,
    pub front_page_number_format: String,
    pub front_page_number_position: String,
    pub front_page_number_size: String,
    pub front_page_number_language: String,
    pub indent_first_line: bool,
    pub indent_amount: String,
    pub center_headings: bool,
    pub bold_headings: bool,
    pub paragraph_spacing: String,
    pub include_toc: bool,
    pub beautify_toc: bool,
    pub toc_language: String,
    pub toc_alignment: String,
    pub toc_design: String,
    pub page_border: bool,
    pub hyphenation: bool,
    pub line_height: String,
    pub copy_friendly_text: bool,
    pub output_name: String,
    pub output_directory: String,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            theme_mode: "system".into(),
            highlight_style: "tango".into(),
            page_size_choice: "A4".into(), orientation: "Portrait".into(),
            margin_choice: "Page default".into(), custom_margin: "25mm".into(),
            font_size_choice: "Medium".into(), custom_font_size: 14.0,
            english_font: "DejaVu Sans".into(), heading_font: "DejaVu Sans".into(),
            bengali_font: "SolaimanLipi".into(), arabic_font: "Amiri".into(),
            code_font: "JetBrains Mono".into(), page_numbers: false,
            page_number_style: "arabic".into(), page_number_format: "Page 1 of 10".into(),
            page_number_position: "Middle".into(), page_number_size: "9pt".into(),
            page_number_language: "English".into(), front_page_numbers: false,
            front_page_number_style: "roman".into(), front_page_number_format: "1".into(),
            front_page_number_position: "Middle".into(), front_page_number_size: "9pt".into(),
            front_page_number_language: "English".into(), indent_first_line: false,
            indent_amount: "0.25in".into(), center_headings: true, bold_headings: true,
            paragraph_spacing: "6pt".into(), include_toc: true, beautify_toc: true,
            toc_language: "English".into(), toc_alignment: "Center".into(),
            toc_design: "Classic".into(), page_border: false, hyphenation: true,
            line_height: "1.1".into(), copy_friendly_text: false,
            output_name: String::new(), output_directory: output_dir().to_string_lossy().into_owned(),
        }
    }
}

pub fn builtin_profiles() -> BTreeMap<String, Settings> {
    let mut profiles = BTreeMap::new();
    profiles.insert("Mobile".into(), Settings { page_size_choice: "For Mobile".into(), font_size_choice: "Standard".into(), line_height: "1.0".into(), ..Default::default() });
    profiles.insert("PC".into(), Settings { page_size_choice: "For PC".into(), font_size_choice: "Medium".into(), line_height: "1.15".into(), ..Default::default() });
    profiles.insert("English".into(), Settings::default());
    profiles.insert("Bangla".into(), Settings { toc_language: "Bangla".into(), page_number_language: "Bangla".into(), ..Default::default() });
    profiles
}

pub const ENGLISH_FONTS: &[&str] = &["DejaVu Sans", "Noto Sans", "Noto Serif", "Source Serif 4", "Inter", "JetBrains Mono", "EB Garamond", "Georgia", "Sabon", "Adobe Garamond", "Minion Pro", "Alegreya", "Alegreya Sans", "Palatino Linotype", "Crimson Text", "Della Respira", "Sylfaen"];
pub const BENGALI_FONTS: &[&str] = &["SolaimanLipi", "Noto Sans Bengali", "Noto Serif Bengali", "Kalpurush", "Ekushey Lalsalu"];
pub const ARABIC_FONTS: &[&str] = &["Amiri", "Noto Naskh Arabic", "Noto Sans Arabic", "Scheherazade New"];
pub const HEADING_FONTS: &[&str] = &["DejaVu Sans", "Noto Sans", "Noto Serif", "Source Serif 4", "Inter", "JetBrains Mono", "EB Garamond", "Georgia", "Sabon", "Adobe Garamond", "Minion Pro", "Alegreya", "Alegreya Sans", "Palatino Linotype", "Crimson Text", "Della Respira", "Sylfaen", "Helvetica", "Arial", "Baskerville", "Libre Baskerville", "Futura", "Playfair Display"];
pub const CODE_FONTS: &[&str] = &["JetBrains Mono", "MonoLisa", "Operator Mono", "DejaVu Sans"];
