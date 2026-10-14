use crate::config::{data_dir, builtin_profiles, Settings};
use anyhow::{Context, Result};
use serde_json::{Map, Value};
use std::{collections::BTreeMap, fs, path::PathBuf};

const REMOVED: &[&str] = &[
    "Book Print - EB Garamond", "Book Print - Alegreya", "Book Print - Crimson Text",
    "Book Print - Georgia", "Minimal", "Decorative", "Profile_1", "Custome_1",
    "Novel Preset", "Georgia-Arial", "Bangla_Update", "Storybook Preset",
];

pub fn path() -> PathBuf {
    let target=data_dir().join("profiles.json");
    if !target.exists() {
        if let Some(local)=std::env::var_os("LOCALAPPDATA") {
            let legacy=PathBuf::from(local).join("Markdown to PDF Studio/profiles.json");
            if legacy.is_file() { let _=fs::create_dir_all(target.parent().unwrap_or_else(||std::path::Path::new("."))); let _=fs::copy(legacy,&target); }
        }
    }
    target
}

fn read_root() -> Map<String, Value> {
    fs::read_to_string(path()).ok().and_then(|s| serde_json::from_str::<Value>(&s).ok())
        .and_then(|v| v.as_object().cloned()).unwrap_or_default()
}

pub fn load_profiles() -> BTreeMap<String, Settings> {
    let mut result = builtin_profiles();
    for (name, value) in read_root() {
        if REMOVED.contains(&name.as_str()) || name == "_last_used" { continue; }
        // The Python app merged partial saved profiles over that profile's
        // defaults. Preserve that behavior for old profiles and hand-edited
        // JSON instead of replacing a built-in preset with generic defaults.
        let mut merged = serde_json::to_value(
            result.get(&name).cloned().unwrap_or_default()
        ).unwrap_or_else(|_| serde_json::json!({}));
        if let (Some(base), Some(overrides)) = (merged.as_object_mut(), value.as_object()) {
            for (key, value) in overrides {
                base.insert(key.clone(), value.clone());
            }
        } else {
            continue;
        }
        if let Ok(saved) = serde_json::from_value::<Settings>(merged) {
            result.insert(name, saved);
        }
    }
    result
}

pub fn last_used() -> Option<(Settings, Option<String>)> {
    let value = read_root().remove("_last_used")?;
    let selected = value.get("selected_profile").and_then(Value::as_str).map(str::to_owned);
    Some((serde_json::from_value(value).ok()?, selected))
}

fn write_root(data: Map<String, Value>) -> Result<()> {
    let target = path();
    fs::create_dir_all(target.parent().context("profile path has no parent")?)?;
    fs::write(&target, serde_json::to_vec_pretty(&data)?).with_context(|| format!("saving {}", target.display()))
}

pub fn save_profile(name: &str, settings: &Settings) -> Result<()> {
    let name=name.trim();
    if name.is_empty() || name == "_last_used" || builtin_profiles().contains_key(name) || REMOVED.contains(&name) {
        anyhow::bail!("Choose a valid name that is not reserved for a built-in profile.");
    }
    let mut root = read_root();
    root.insert(name.to_owned(), serde_json::to_value(settings)?);
    write_root(root)
}

pub fn update_profile(name: &str, settings: &Settings) -> Result<()> {
    let mut root = read_root();
    if builtin_profiles().contains_key(name) || root.contains_key(name) {
        root.insert(name.to_owned(), serde_json::to_value(settings)?);
        write_root(root)
    } else { anyhow::bail!("Only an existing profile can be updated.") }
}

pub fn delete_profile(name: &str) -> Result<()> {
    if builtin_profiles().contains_key(name) || REMOVED.contains(&name) || name == "_last_used" {
        anyhow::bail!("Built-in and internal profiles cannot be deleted.");
    }
    let mut root = read_root();
    if root.remove(name).is_none() { anyhow::bail!("The selected profile no longer exists."); }
    write_root(root)
}

pub fn save_last_used(settings: &Settings, selected: &str) -> Result<()> {
    let mut value = serde_json::to_value(settings)?;
    value.as_object_mut().context("serialized settings were not an object")?
        .insert("selected_profile".into(), Value::String(selected.to_owned()));
    let mut root = read_root();
    root.insert("_last_used".into(), value);
    write_root(root)
}
