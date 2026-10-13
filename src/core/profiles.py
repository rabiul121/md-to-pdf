"""
Profile management and configuration persistence.
"""

import json
from pathlib import Path
from src.core.constants import (
    PROFILE_PATH,
    LAST_USED_PROFILE,
    PROFILE_BASE_SETTINGS,
    BUILT_IN_PROFILES,
    REMOVED_BUILT_IN_PROFILES,
)


def _read_saved_profiles():
    """Read profiles.json as a dict, tolerating missing or invalid files."""
    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
            saved_profiles = json.load(profile_file)
        if not isinstance(saved_profiles, dict):
            saved_profiles = {}
    except (OSError, json.JSONDecodeError):
        saved_profiles = {}
    return saved_profiles


def _guard_profile_name(name):
    """Reject internal names and names of removed built-in presets."""
    if name == LAST_USED_PROFILE:
        raise ValueError("Built-in and internal profiles cannot be overwritten.")
    if name in REMOVED_BUILT_IN_PROFILES:
        raise ValueError(
            f"'{name}' was a built-in profile that has been removed. "
            "Save it under a new custom name instead."
        )


def load_profiles():
    """Load built-in presets and saved profiles, preserving user profiles.

    Overrides saved for built-ins that were removed in the redesign (the four
    Book Print presets plus Minimal and Decorative) are treated as legacy data
    and skipped. Every other saved profile name is preserved.
    """
    saved_profiles = _read_saved_profiles()

    profiles = {
        name: {**PROFILE_BASE_SETTINGS, **settings}
        for name, settings in BUILT_IN_PROFILES.items()
    }
    for name, settings in saved_profiles.items():
        if name in REMOVED_BUILT_IN_PROFILES:
            continue
        if isinstance(settings, dict) and name in BUILT_IN_PROFILES:
            profiles[name] = {**profiles[name], **settings}
        elif isinstance(settings, dict) and name != LAST_USED_PROFILE:
            profiles[name] = {**PROFILE_BASE_SETTINGS, **settings}
    return profiles


def save_profile(name, settings):
    """Persist one named conversion profile."""
    _guard_profile_name(name)
    if name in BUILT_IN_PROFILES:
        raise ValueError("Built-in and internal profiles cannot be overwritten.")
    saved_profiles = _read_saved_profiles()
    saved_profiles[name] = settings
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_PATH.open("w", encoding="utf-8") as profile_file:
        json.dump(saved_profiles, profile_file, ensure_ascii=False, indent=2)


def update_profile(name, settings):
    """Persist edits to an existing built-in or user-created profile."""
    if not name:
        raise ValueError("Select a profile to update.")
    _guard_profile_name(name)
    saved_profiles = _read_saved_profiles()
    if name not in BUILT_IN_PROFILES and name not in saved_profiles:
        raise ValueError("Only an existing profile can be updated.")
    saved_profiles[name] = settings
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_PATH.open("w", encoding="utf-8") as profile_file:
        json.dump(saved_profiles, profile_file, ensure_ascii=False, indent=2)


def load_last_used_settings():
    """Load the last GUI settings and selected profile, if available."""
    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
            saved_profiles = json.load(profile_file)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(saved_profiles, dict):
        return {}
    settings = saved_profiles.get(LAST_USED_PROFILE, {})
    return settings if isinstance(settings, dict) else {}


def save_last_used_settings(settings, selected_profile=None):
    """Persist the most recent GUI configuration for the next application launch."""
    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
            saved_profiles = json.load(profile_file)
        if not isinstance(saved_profiles, dict):
            saved_profiles = {}
    except (OSError, json.JSONDecodeError):
        saved_profiles = {}
    saved_settings = dict(settings)
    if selected_profile:
        saved_settings["selected_profile"] = selected_profile
    saved_profiles[LAST_USED_PROFILE] = saved_settings
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_PATH.open("w", encoding="utf-8") as profile_file:
        json.dump(saved_profiles, profile_file, ensure_ascii=False, indent=2)


def delete_profile(name):
    """Delete a user-created profile without changing built-in presets."""
    if name in BUILT_IN_PROFILES or name in REMOVED_BUILT_IN_PROFILES or name == LAST_USED_PROFILE:
        raise ValueError("Built-in and internal profiles cannot be deleted.")
    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
            saved_profiles = json.load(profile_file)
    except (OSError, json.JSONDecodeError):
        return False
    if name not in saved_profiles:
        return False
    del saved_profiles[name]
    with PROFILE_PATH.open("w", encoding="utf-8") as profile_file:
        json.dump(saved_profiles, profile_file, ensure_ascii=False, indent=2)
    return True
