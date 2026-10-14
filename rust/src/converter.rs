use crate::config::{resource_dir, Settings, SUPPORTED_EXTENSIONS};
use anyhow::{anyhow, Context, Result};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{collections::HashMap, fs, path::{Path, PathBuf}, process::{Command, Stdio}};

#[derive(Clone, Debug)]
pub struct ConvertResult { pub input: PathBuf, pub output: Option<PathBuf>, pub error: Option<String> }

fn executable(name: &str) -> Option<PathBuf> {
    if let Ok(path) = which::which(name) { return Some(path); }
    #[cfg(windows)] {
        let local = std::env::var_os("LOCALAPPDATA").map(PathBuf::from);
        let user = std::env::var_os("USERPROFILE").map(PathBuf::from);
        let candidates = match (name, local, user) {
            ("pandoc", Some(local), _) => vec![local.join("Pandoc/pandoc.exe")],
            ("xelatex", _, Some(user)) => vec![user.join("scoop/apps/miktex/current/texmfs/install/miktex/bin/x64/xelatex.exe")],
            _ => Vec::new(),
        };
        return candidates.into_iter().find(|path| path.exists());
    }
    #[cfg(not(windows))]
    None
}

fn unique_output(path: &Path) -> PathBuf {
    if !path.exists() { return path.to_path_buf(); }
    let stem = path.file_stem().and_then(|s| s.to_str()).unwrap_or("document");
    let ext = path.extension().and_then(|s| s.to_str()).unwrap_or("pdf");
    for index in 1.. {
        let candidate = path.with_file_name(format!("{stem}_{index}.{ext}"));
        if !candidate.exists() { return candidate; }
    }
    unreachable!()
}

fn bundled_font(family: &str, role: &str) -> Option<(String, PathBuf)> {
    let (folder, file) = match (role, family) {
        ("english", "DejaVu Sans") => ("english", "DejaVuSans-Regular.ttf"),
        ("english", "Noto Sans") => ("english", "NotoSans-VariableFont_wdth,wght.ttf"),
        ("english", "Noto Serif") => ("english", "NotoSerif-VariableFont_wdth,wght.ttf"),
        ("english", "Source Serif 4") => ("english", "SourceSerif4-VariableFont_opsz,wght.ttf"),
        ("english", "Inter") => ("english", "Inter-VariableFont_opsz,wght.ttf"),
        ("english", "JetBrains Mono") => ("english", "JetBrainsMono-VariableFont_wght.ttf"),
        ("english", "EB Garamond") => ("english", "EBGaramond-Variable.ttf"),
        ("english", "Georgia") => ("english", "Georgia-Regular.ttf"),
        ("english", "Sabon") => ("english", "Sabon-Regular.ttf"),
        ("english", "Adobe Garamond") => ("english", "AdobeGaramondPro-Regular.otf"),
        ("english", "Minion Pro") => ("english", "MinionPro-Regular.otf"),
        ("english", "Alegreya") => ("english", "Alegreya-Variable.ttf"),
        ("english", "Alegreya Sans") => ("english", "AlegreyaSans-Regular.ttf"),
        ("english", "Palatino Linotype") => ("english", "PalatinoLinotype-Regular.ttf"),
        ("english", "Crimson Text") => ("english", "CrimsonText-Regular.ttf"),
        ("english", "Della Respira") => ("english", "DellaRespira-Regular.ttf"),
        ("english", "Sylfaen") => ("english", "Sylfaen-Regular.ttf"),
        ("english", "Baskerville") => ("english", "Baskerville-Regular.ttf"),
        ("english", "Libre Baskerville") => ("english", "LibreBaskerville-Variable.ttf"),
        ("english", "Helvetica") => ("english", "Helvetica.ttf"),
        ("english", "Arial") => ("english", "Arial-Regular.ttf"),
        ("english", "Futura") => ("english", "FuturaLTPro-Book.otf"),
        ("english", "Playfair Display") => ("english", "PlayfairDisplay-Variable.ttf"),
        ("bengali", "SolaimanLipi") => ("bengali", "SolaimanLipi-Regular.ttf"),
        ("bengali", "Noto Sans Bengali") => ("bengali", "NotoSansBengali-VariableFont_wdth,wght.ttf"),
        ("bengali", "Noto Serif Bengali") => ("bengali", "NotoSerifBengali-VariableFont_wdth,wght.ttf"),
        ("bengali", "Kalpurush") => ("bengali", "Kalpurush-Regular.ttf"),
        ("bengali", "Ekushey Lalsalu") => ("bengali", "EkusheyLalsalu-Regular.ttf"),
        ("arabic", "Amiri") => ("arabic", "Amiri-Regular.ttf"),
        ("arabic", "Noto Naskh Arabic") => ("arabic", "NotoNaskhArabic-VariableFont_wght.ttf"),
        ("arabic", "Noto Sans Arabic") => ("arabic", "NotoSansArabic-VariableFont_wdth,wght.ttf"),
        ("arabic", "Scheherazade New") => ("arabic", "ScheherazadeNew-Regular.ttf"),
        ("coding" | "coading", "JetBrains Mono") => ("english", "JetBrainsMono-VariableFont_wght.ttf"),
        ("coding" | "coading", "MonoLisa") => ("coading", "MonoLisa-Regular.ttf"),
        ("coding" | "coading", "Operator Mono") => ("coading", "OperatorMono-Book.ttf"),
        ("coding" | "coading", "DejaVu Sans") => ("english", "DejaVuSans-Regular.ttf"),
        ("symbol", "Noto Emoji") => ("symbol", "NotoEmoji-VariableFont_wght.ttf"),
        ("symbol", "Noto Sans Symbols 2") => ("symbol", "NotoSansSymbols2-Regular.ttf"),
        ("symbol", "Segoe UI Emoji") => ("symbol", "seguiemj.ttf"),
        ("symbol", "Segoe UI Symbol") => ("symbol", "seguisym.ttf"),
        _ => return None,
    };
    let base = resource_dir().join("assets/fonts").join(folder);
    let path = base.join(file);
    path.is_file().then(|| (file.to_owned(), base))
}

fn resolve_font(family: &str, role: &str) -> Option<(String, PathBuf)> {
    if let Some(font) = bundled_font(family, role) { return Some(font); }
    let output = Command::new("fc-match").args(["-f", "%{family}\n%{file}", family]).output().ok()?;
    if !output.status.success() { return None; }
    let text = String::from_utf8_lossy(&output.stdout);
    let mut lines = text.lines();
    let families = lines.next()?.split(',').map(|s| s.trim().to_lowercase()).collect::<Vec<_>>();
    if !families.iter().any(|name| name == &family.to_lowercase()) { return None; }
    let file = PathBuf::from(lines.next()?.trim());
    Some((file.file_name()?.to_string_lossy().into_owned(), file.parent()?.to_path_buf()))
}

fn font_features(font: &(String, PathBuf)) -> String {
    let path = Path::new(&font.0);
    let stem = path.file_stem().and_then(|s| s.to_str()).unwrap_or("");
    let base = stem.strip_suffix("-Regular").or_else(|| stem.strip_suffix("-Book")).unwrap_or(stem);
    let find = |suffix: &str| {
        let candidate = font.1.join(format!("{base}-{suffix}.{}", path.extension()?.to_str()?));
        candidate.exists().then(|| candidate.file_name().map(|name| name.to_string_lossy().into_owned())).flatten()
    };
    let bold = find("Bold"); let italic = find("Italic").or_else(|| find("It")).or_else(|| find("Oblique")).or_else(|| find("RegularItalic")).or_else(|| find("BookItalic"));
    let bolditalic = find("BoldItalic").or_else(|| find("BoldIt")).or_else(|| find("BoldOblique"));
    let mut result = format!("BoldFont={{{}}}", bold.as_deref().unwrap_or(&font.0));
    if bold.is_none() { result.push_str(",BoldFeatures={FakeBold=2}"); }
    result.push_str(&format!(",ItalicFont={{{}}}", italic.as_deref().unwrap_or(&font.0)));
    if italic.is_none() { result.push_str(",ItalicFeatures={FakeSlant=0.2}"); }
    result.push_str(&format!(",BoldItalicFont={{{}}}", bolditalic.as_deref().or(italic.as_deref()).or(bold.as_deref()).unwrap_or(&font.0)));
    if bolditalic.is_none() {
        let mut features=Vec::new();
        if italic.is_some() || bold.is_none() { features.push("FakeBold=2"); }
        if italic.is_none() { features.push("FakeSlant=0.2"); }
        if !features.is_empty() { result.push_str(&format!(",BoldItalicFeatures={{{}}}",features.join(","))); }
    }
    result
}

fn supports_codepoint(font: &(String, PathBuf), cp: u32) -> bool {
    let path = font.1.join(&font.0);
    if let (Some(character), Ok(data)) = (char::from_u32(cp), fs::read(&path)) {
        let face_count=ttf_parser::fonts_in_collection(&data).unwrap_or(1);
        for index in 0..face_count {
            if let Ok(face)=ttf_parser::Face::parse(&data,index) {
                if face.glyph_index(character).is_some() { return true; }
            }
        }
    }
    let output = Command::new("fc-query").args(["-f", "%{charset}"]).arg(path).output();
    let Ok(output) = output else { return false; };
    if !output.status.success() { return false; }
    let target = cp as u64;
    String::from_utf8_lossy(&output.stdout).split_whitespace().any(|range| {
        let mut it = range.split('-');
        let start = u64::from_str_radix(it.next().unwrap_or(""), 16).unwrap_or(u64::MAX);
        let end = it.next().and_then(|v| u64::from_str_radix(v, 16).ok()).unwrap_or(start);
        (start..=end).contains(&target)
    })
}

fn put_font_vars(vars: &mut Vec<(String, String)>, key: &str, name: &str, selection: Option<(String, PathBuf)>, with_features: bool) {
    if let Some((file, dir)) = selection {
        vars.push((format!("{key}file"), file.clone()));
        vars.push((format!("{key}path"), format!("{}/", dir.to_string_lossy().replace('\\', "/"))));
        if with_features { vars.push((format!("{key}features"), font_features(&(file, dir)))); }
    }
    let _ = name;
}

fn expand_output_directory(value: &str) -> PathBuf {
    let home = std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME"));
    if value == "~" {
        return home.map(PathBuf::from).unwrap_or_else(|| PathBuf::from(value));
    }
    if let Some(rest) = value.strip_prefix("~/").or_else(|| value.strip_prefix("~\\")) {
        if let Some(home) = home { return PathBuf::from(home).join(rest); }
    }
    PathBuf::from(value)
}

fn output_path(input: &Path, settings: &Settings, forced_name: Option<&str>) -> Result<PathBuf> {
    let directory = if settings.output_directory.trim().is_empty() { crate::config::output_dir() } else { expand_output_directory(settings.output_directory.trim()) };
    let mut name = if !settings.output_name.trim().is_empty() { settings.output_name.clone() }
        else { forced_name.map(str::to_owned).filter(|s| !s.trim().is_empty()).unwrap_or_else(|| input.file_stem().and_then(|s| s.to_str()).unwrap_or("Document").to_owned()) };
    name = name.trim().to_owned();
    if Path::new(&name).file_name().and_then(|s| s.to_str()) != Some(name.as_str()) || name.is_empty() {
        anyhow::bail!("Output filename must be a name, not a path.");
    }
    if name.to_lowercase().ends_with(".pdf") { name.truncate(name.len() - 4); }
    let path = directory.join(format!("{name}.pdf"));
    fs::create_dir_all(path.parent().unwrap_or(&directory))?;
    Ok(unique_output(&path))
}

fn markdown_json_with_local_images(source: &Path, pandoc: &Path, scratch: &Path, log: &mut dyn FnMut(String)) -> Result<Option<PathBuf>> {
    let input = fs::read_to_string(source).context("reading Markdown before remote image handling")?;
    if !input.contains("http://") && !input.contains("https://") { return Ok(None); }
    let result = Command::new(pandoc).arg(source).args(["--from=markdown", "--to=json"]).output()?;
    if !result.status.success() { anyhow::bail!("Pandoc could not parse the document for remote image handling: {}",String::from_utf8_lossy(&result.stderr)); }
    let mut doc: Value = serde_json::from_slice(&result.stdout)?;
    let client = reqwest::blocking::Client::builder().user_agent("Mozilla/5.0").timeout(std::time::Duration::from_secs(30)).build()?;
    let mut downloaded: HashMap<String, Option<String>> = HashMap::new();
    fn walk(value: &mut Value, scratch: &Path, client: &reqwest::blocking::Client, downloaded: &mut HashMap<String, Option<String>>, log: &mut dyn FnMut(String)) {
        let replacement = if let Value::Object(obj)=value {
            let url = if obj.get("t").and_then(Value::as_str)==Some("Image") {
                obj.get("c").and_then(Value::as_array).and_then(|v|v.get(2)).and_then(Value::as_array).and_then(|v|v.first()).and_then(Value::as_str).unwrap_or("").to_owned()
            } else { String::new() };
            if url.starts_with("http://")||url.starts_with("https://") {
                if !downloaded.contains_key(&url) {
                    let local=(||->std::result::Result<String,String>{
                        use std::io::Read;
                        let mut response=client.get(&url).header(reqwest::header::ACCEPT,"image/png,image/jpeg,image/*;q=0.8,*/*;q=0.5").send().and_then(|r|r.error_for_status()).map_err(|e|e.to_string())?;
                        if response.content_length().is_some_and(|size|size>25*1024*1024){return Err("Image exceeds the 25 MB download limit".into());}
                        let mut bytes=Vec::new();response.by_ref().take(25*1024*1024+1).read_to_end(&mut bytes).map_err(|e|e.to_string())?;
                        if bytes.len()>25*1024*1024{return Err("Image exceeds the 25 MB download limit".into());}
                        let ext=if bytes.starts_with(b"\x89PNG\r\n\x1a\n"){"png"}else if bytes.starts_with(b"\xff\xd8\xff"){"jpg"}else if bytes.starts_with(b"%PDF-"){"pdf"}else{return Err("URL did not return a supported PNG, JPEG, or PDF image".into());};
                        let hash=format!("{:x}",Sha256::digest(url.as_bytes()));let path=scratch.join(format!("{hash}.{ext}"));
                        fs::write(&path,bytes).map_err(|e|e.to_string())?;Ok(path.to_string_lossy().replace('\\',"/"))
                    })();
                    match local {Ok(path)=>{downloaded.insert(url.clone(),Some(path));log("[IMAGE] Downloaded remote image".into());},Err(error)=>{downloaded.insert(url.clone(),None);log(format!("[WARNING] Could not download image {url}: {error}"));}}
                }
                if let Some(Some(local))=downloaded.get(&url) {
                    if let Some(target)=obj.get_mut("c").and_then(Value::as_array_mut).and_then(|v|v.get_mut(2)).and_then(Value::as_array_mut).and_then(|v|v.first_mut()){*target=Value::String(local.clone());}
                    None
                } else {
                    let content=obj.get("c").and_then(Value::as_array).cloned().unwrap_or_default();
                    if content.len()>=2 {Some(serde_json::json!({"t":"Span","c":[content[0],content[1]]}))}else{None}
                }
            } else {None}
        }else{None};
        if let Some(replacement)=replacement { *value=replacement;return; }
        match value {
            Value::Array(items)=>for item in items{walk(item,scratch,client,downloaded,log)},
            Value::Object(obj)=>for child in obj.values_mut(){walk(child,scratch,client,downloaded,log)},
            _=>{}
        }
    }
    walk(&mut doc, scratch, &client, &mut downloaded, log);
    if downloaded.is_empty() { return Ok(None); }
    let target = scratch.join("document.json");
    fs::write(&target, serde_json::to_vec(&doc)?)?;
    Ok(Some(target))
}

fn escape_plain(text: &str) -> String {
    let punctuation = r##"!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"##;
    text.chars().flat_map(|c| if punctuation.contains(c) { vec!['\\', c] } else { vec![c] }).collect()
}

fn variables(settings: &Settings) -> Vec<(String, String)> {
    let mut vars = Vec::new();
    let fontsize = effective_font_size(settings);
    let lineheight = settings.line_height.parse::<f32>().ok().filter(|value| value.is_finite()).unwrap_or(1.1).clamp(0.7, 2.5).to_string();
    let spacing = if settings.paragraph_spacing.trim().is_empty() { "6pt" } else { settings.paragraph_spacing.trim() };
    let valid_spacing = regexless_spacing(spacing).then(|| spacing.to_owned()).unwrap_or_else(|| "6pt".into());
    vars.extend([
        ("fontsize".into(), fontsize), ("fontenglish".into(), settings.english_font.clone()),
        ("fontheading".into(), settings.heading_font.clone()), ("fontbengali".into(), settings.bengali_font.clone()),
        ("fontarabic".into(), settings.arabic_font.clone()), ("fontmono".into(), settings.code_font.clone()),
        ("indentamount".into(), settings.indent_amount.clone()), ("paragraphspacing".into(), valid_spacing),
        ("lineheight".into(), lineheight), ("pagenumberstyle".into(), settings.page_number_style.clone()),
        ("pagenumbersize".into(), settings.page_number_size.clone()),
        ("pagenumberposition".into(), match settings.page_number_position.as_str() { "Bottom left" => "L", "Bottom right" => "R", _ => "C" }.into()),
        ("frontpagenumberstyle".into(), settings.front_page_number_style.clone()),
        ("frontpagenumbersize".into(), settings.front_page_number_size.clone()),
        ("frontpagenumberposition".into(), match settings.front_page_number_position.as_str() { "Bottom left" => "L", "Bottom right" => "R", _ => "C" }.into()),
        ("fontcurrency".into(), if cfg!(windows) { "Segoe UI".into() } else { settings.english_font.clone() }),
        ("fontemoji".into(), if cfg!(windows) { "Segoe UI Emoji" } else { "Noto Emoji" }.into()),
        ("fontsymbol".into(), if cfg!(windows) { "Segoe UI Symbol" } else { "Noto Sans Symbols 2" }.into()),
    ]);
    let flags = [
        ("pagenumbers", settings.page_numbers), ("firstlineindent", settings.indent_first_line),
        ("centerheadings", settings.center_headings), ("boldheadings", settings.bold_headings),
        ("beautifytoc", settings.beautify_toc), ("pageborder", settings.page_border),
        ("toclanguagebangla", settings.toc_language == "Bangla"),
        ("pagenumberlanguagebangla", settings.page_number_language == "Bangla"),
        ("frontpagenumbers", settings.front_page_numbers && settings.include_toc),
        ("frontpagenumberlanguagebangla", settings.front_page_number_language == "Bangla"),
        ("tocpagebangla", settings.toc_language == "Bangla"), ("hyphenation", settings.hyphenation),
        ("copyfriendlytext", settings.copy_friendly_text),
    ];
    for (key, enabled) in flags { if enabled { vars.push((key.into(), "true".into())); } }
    if settings.include_toc { vars.push(("toc".into(), "true".into())); }
    vars.push(("toctitlealignment".into(), match settings.toc_alignment.as_str() { "Left" => "", "Right" => r"\hfill", _ => r"\hfill" }.into()));
    vars.push(("toctitleendfill".into(), match settings.toc_alignment.as_str() { "Right" => "", _ => r"\hfill" }.into()));
    vars.push(("toctitlesize".into(), "16pt".into()));
    let page_format = |format: &str, bangla: bool| -> String {
        match (format, bangla) {
            ("1 / 10", false) => r"\thepage\ / \pageref*{LastPage}".into(),
            ("Page 1", false) => r"Page~\thepage".into(),
            ("1", false) => r"\thepage".into(),
            ("1 / 10", true) => r"{\bangladigits{\getpagerefnumber{LastPage}}}~ / ~{\bangladigits{\arabic{page}}}".into(),
            ("Page 1", true) => r"{\bengalifont পৃষ্ঠা}~{\bangladigits{\arabic{page}}}".into(),
            ("1", true) => r"{\bangladigits{\arabic{page}}}".into(),
            (_, true) => r"{\bengalifont পৃষ্ঠা}~{\bangladigits{\getpagerefnumber{LastPage}}}~{\bengalifont এর}~{\bangladigits{\arabic{page}}}".into(),
            (_, false) => r"Page~\thepage\ of~\pageref*{LastPage}".into(),
        }
    };
    let front_page_format = |format: &str, bangla: bool| -> String {
        match (format, bangla) {
            ("Page 1 of 10", false) => r"Page~\thepage\ of~\getpagerefnumber{FrontMatterLastPage}".into(),
            ("1 / 10", false) => r"\thepage\ / \getpagerefnumber{FrontMatterLastPage}".into(),
            ("Page 1", false) => r"Page~\thepage".into(),
            ("Page 1 of 10", true) => r"{\bengalifont পৃষ্ঠা}~{\bangladigits{\getpagerefnumber{FrontMatterLastPage}}}~{\bengalifont এর}~{\bangladigits{\arabic{page}}}".into(),
            ("1 / 10", true) => r"{\bangladigits{\arabic{page}}}~ / ~{\bangladigits{\getpagerefnumber{FrontMatterLastPage}}}".into(),
            ("Page 1", true) => r"{\bengalifont পৃষ্ঠা}~{\bangladigits{\arabic{page}}}".into(),
            (_, true) => r"{\bangladigits{\arabic{page}}}".into(),
            (_, false) => r"\thepage".into(),
        }
    };
    vars.push(("pagenumbertext".into(), page_format(&settings.page_number_format, false)));
    vars.push(("pagenumbertextbangla".into(), page_format(&settings.page_number_format, true)));
    vars.push(("frontpagenumbertext".into(), front_page_format(&settings.front_page_number_format, false)));
    vars.push(("frontpagenumbertextbangla".into(), front_page_format(&settings.front_page_number_format, true)));
    let (title_color, entry_color, after) = match settings.toc_design.as_str() {
        "Minimal" => ("black", "black", r"\par\medskip"),
        "Decorative" => ("teal!65!black", "teal!55!black", r"\par\medskip\hrule height 1pt\bigskip"),
        _ => ("blue!65!black", "blue!55!black", r"\par\medskip\hrule\bigskip"),
    };
    vars.push(("toctitlecolor".into(), title_color.into())); vars.push(("tocentrycolor".into(), entry_color.into())); vars.push(("tocaftertitle".into(), after.into()));
    let english = resolve_font(&settings.english_font,"english");
    let selected_heading = resolve_font(&settings.heading_font,"english");
    let heading_latin = selected_heading.clone().filter(|f|supports_codepoint(f,0x0041)).or_else(||english.clone());
    let heading_bengali = selected_heading.filter(|f|supports_codepoint(f,0x0985)).or_else(||resolve_font(&settings.bengali_font,"bengali"));
    for (key, font, selection) in [("fontenglish", settings.english_font.as_str(), english), ("fontheadinglatin", settings.heading_font.as_str(), heading_latin), ("fontheadingbengali", settings.heading_font.as_str(), heading_bengali), ("fontbengali", settings.bengali_font.as_str(), resolve_font(&settings.bengali_font,"bengali")), ("fontarabic", settings.arabic_font.as_str(), resolve_font(&settings.arabic_font,"arabic")), ("fontmono", settings.code_font.as_str(), resolve_font(&settings.code_font,"coding").or_else(||resolve_font(&settings.code_font,"english")).or_else(||bundled_font("JetBrains Mono","coding")))] {
        put_font_vars(&mut vars, key, font, selection, matches!(key, "fontenglish" | "fontbengali" | "fontarabic" | "fontmono"));
    }
    if let Some((file, dir)) = bundled_font(if cfg!(windows) { "Segoe UI Emoji" } else { "Noto Emoji" }, "symbol") { put_font_vars(&mut vars, "fontemoji", "", Some((file, dir)), false); }
    if let Some((file, dir)) = bundled_font(if cfg!(windows) { "Segoe UI Symbol" } else { "Noto Sans Symbols 2" }, "symbol") { put_font_vars(&mut vars, "fontsymbol", "", Some((file, dir)), false); }
    if let Some((file, dir)) = bundled_font("Noto Emoji", "symbol") { put_font_vars(&mut vars, "fontemojiSupplement", "", Some((file, dir)), false); }
    vars
}

fn effective_font_size(settings: &Settings) -> String {
    match settings.font_size_choice.as_str() {
        "Standard" => "11pt".into(),
        "Large" => "17pt".into(),
        "Custom" => format!("{}pt", settings.custom_font_size.max(1.0)),
        _ => "14pt".into(),
    }
}

fn regexless_spacing(value: &str) -> bool {
    let suffix = ["pt", "mm", "cm", "in", "em"].iter().find(|s| value.ends_with(**s));
    suffix.is_some_and(|suffix| {
        let number=&value[..value.len()-suffix.len()];
        let valid_digits=|part:&str| !part.is_empty()&&part.bytes().all(|byte|byte.is_ascii_digit());
        let valid_number=if let Some((whole,fraction))=number.split_once('.') {
            valid_digits(whole)&&valid_digits(fraction)&&!fraction.contains('.')
        } else { valid_digits(number) };
        valid_number&&number.parse::<f32>().is_ok_and(|value|value.is_finite()&&value>=0.0)
    })
}

pub fn convert_one(input: &Path, settings: &Settings, input_format: Option<&str>, forced_name: Option<&str>, log: &mut dyn FnMut(String)) -> Result<PathBuf> {
    let input = input.canonicalize().with_context(|| format!("input does not exist: {}", input.display()))?;
    let ext = input.extension().and_then(|s| s.to_str()).unwrap_or("").to_lowercase();
    if !SUPPORTED_EXTENSIONS.contains(&ext.as_str()) { anyhow::bail!("Unsupported input type '.{ext}'."); }
    let pandoc = executable("pandoc").ok_or_else(|| anyhow!("Pandoc was not found."))?;
    let xelatex = executable("xelatex").ok_or_else(|| anyhow!("XeLaTeX was not found."))?;
    let output = output_path(&input, settings, forced_name)?;
    let scratch = tempfile::tempdir()?;
    let mut source = input.clone();
    if ext == "doc" || ext == "mobi" {
        let adapter = if ext == "doc" { executable("soffice").or_else(|| executable("libreoffice")).ok_or_else(|| anyhow!("LibreOffice is required for .doc files."))? } else { executable("ebook-convert").ok_or_else(|| anyhow!("Calibre (ebook-convert) is required for .mobi files."))? };
        let intermediate = scratch.path().join(format!("{}.{}", input.file_stem().unwrap_or_default().to_string_lossy(), if ext == "doc" { "docx" } else { "epub" }));
        let result = if ext == "doc" { Command::new(adapter).args(["--headless", "--convert-to", "docx", "--outdir"]).arg(scratch.path()).arg(&input).output()? } else { Command::new(adapter).arg(&input).arg(&intermediate).output()? };
        if !result.status.success() || !intermediate.exists() { anyhow::bail!("{}", String::from_utf8_lossy(&result.stderr)); }
        source = intermediate;
    }
    let mut actual_input = source.clone();
    let mut actual_format = input_format.map(str::to_owned);
    let mut plain_file = None;
    if input_format == Some("plain") {
        let literal = scratch.path().join("literal.md");
        let text=fs::read_to_string(&source)?;
        fs::write(&literal, escape_plain(text.strip_prefix('\u{feff}').unwrap_or(&text)))?;
        actual_input = literal.clone(); actual_format = Some("markdown+hard_line_breaks".into()); plain_file = Some(literal);
    } else if input_format.is_none() && ["md", "markdown", "txt"].contains(&ext.as_str()) {
        actual_format = Some("markdown".into());
    }
    if input_format != Some("plain") && ["md", "markdown", "txt"].contains(&ext.as_str()) {
        if let Some(json) = markdown_json_with_local_images(&source, &pandoc, scratch.path(), log)? {
            actual_input = json; actual_format = Some("json".into());
        }
    }
    let _keep_plain = plain_file;
    let root = resource_dir();
    let mut command = Command::new(&pandoc);
    #[cfg(windows)] {
        let scoop_miktex=std::env::var_os("USERPROFILE").map(PathBuf::from)
            .map(|home|home.join("scoop/apps/miktex/current/texmfs/install/miktex/bin/x64"));
        if let Some(directory)=scoop_miktex.filter(|path|path.is_dir()) {
            let current=std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default()).collect::<Vec<_>>();
            let already_present=current.iter().any(|path|path.to_string_lossy().eq_ignore_ascii_case(&directory.to_string_lossy()));
            if !already_present {
                let mut paths=vec![directory];paths.extend(current);
                command.env("PATH",std::env::join_paths(paths).context("adding MiKTeX to the Pandoc environment")?);
            }
        }
    }
    let working_directory=std::env::current_dir().unwrap_or_else(|_|root.clone());
    let resource_paths=vec![source.parent().unwrap_or(&root).to_path_buf(),input.parent().unwrap_or(&root).to_path_buf(),working_directory,root.clone()];
    let resource_path=std::env::join_paths(resource_paths.iter()).context("building Pandoc resource search path")?;
    command.arg(&actual_input).arg("-o").arg(&output)
        .arg(format!("--pdf-engine={}", xelatex.display()))
        .arg(format!("--template={}", root.join("src/template.tex").display()))
        .arg(format!("--lua-filter={}", root.join("src/font_filter.lua").display()))
        .arg(format!("--resource-path={}", resource_path.to_string_lossy()));
    if !settings.highlight_style.trim().is_empty() {
        command.arg(format!("--highlight-style={}",settings.highlight_style.trim()));
    }
    let paper = match settings.page_size_choice.as_str() { "Letter" => "letterpaper", "A5" => "a5paper", "Legal" => "legalpaper", "For Mobile" => "paperwidth=100mm", _ => "a4paper" };
    command.arg("-V").arg(format!("geometry:{paper}"));
    let mut geometry_description=vec![paper.to_owned()];
    if settings.page_size_choice == "For Mobile" { command.arg("-V").arg("geometry:paperheight=160mm"); geometry_description.push("paperheight=160mm".into()); }
    if settings.orientation == "Landscape" { command.arg("-V").arg("geometry:landscape"); geometry_description.push("landscape".into()); }
    let margin = match settings.margin_choice.as_str() {
        "Custom" if !settings.custom_margin.trim().is_empty() => settings.custom_margin.as_str(),
        "Page default" => match settings.page_size_choice.as_str() { "For Mobile" => "7mm", "For PC" => "1.2in", _ => "1in" },
        "Narrow (0.5 in)" => "0.5in", "Standard (1 in)" => "1in", "Wide (1.25 in)" => "1.25in", "Wide (1.5 in)" => "1.5in", "Compact (7 mm)" => "7mm", _ => "1in"
    };
    command.arg("-V").arg(format!("geometry:margin={margin}"));
    geometry_description.push(format!("margin={margin}"));
    if let Some(format) = actual_format { command.arg(format!("--from={format}")); }
    if settings.include_toc { command.arg("--toc"); }
    for (name, value) in variables(settings) { command.arg("-V").arg(format!("{name}={value}")); }
    log(format!("Converting '{}' -> '{}'...", input.file_name().unwrap_or_default().to_string_lossy(), output.file_name().unwrap_or_default().to_string_lossy()));
    log(format!("  • Page Size : {} ({})", settings.page_size_choice, geometry_description.join(", ")));
    log(format!("  • Font Size : {}", effective_font_size(settings)));
    log(format!("  • Fonts     : English={}, Bengali={}, Arabic={}", settings.english_font, settings.bengali_font, settings.arabic_font));
    let result = command.stdout(Stdio::piped()).stderr(Stdio::piped()).output()?;
    if result.status.success() {
        let mut warning_continuation=false;
        for line in String::from_utf8_lossy(&result.stderr).lines() {
            if line.starts_with("[WARNING]") { log(line.into()); warning_continuation=true; }
            else if warning_continuation&&(line.chars().next().is_some_and(char::is_whitespace)||line=="  }") { log(format!("  {}",line.trim())); }
            else { warning_continuation=false; }
        }
        log(format!("[SUCCESS] PDF successfully created: {}", output.display()));
        Ok(output)
    } else {
        log(format!("[ERROR] Pandoc/XeLaTeX conversion failed (Code {}):", result.status.code().unwrap_or(-1)));
        for line in String::from_utf8_lossy(&result.stderr).lines() { log(format!("  {line}")); }
        anyhow::bail!("{}", String::from_utf8_lossy(&result.stderr))
    }
}

pub fn convert_many(inputs: &[PathBuf], settings: &Settings, input_format: Option<&str>, log: &mut dyn FnMut(String)) -> Vec<ConvertResult> {
    inputs.iter().map(|input| {
        let mut file_settings=settings.clone();
        if inputs.len()>1 { file_settings.output_name.clear(); }
        match convert_one(input, &file_settings, input_format, None, log) {
            Ok(output) => ConvertResult { input: input.clone(), output: Some(output), error: None },
            Err(error) => ConvertResult { input: input.clone(), output: None, error: Some(error.to_string()) },
        }
    }).collect()
}
