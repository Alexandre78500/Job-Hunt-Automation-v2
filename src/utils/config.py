from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env() -> None:
    env_path = project_root() / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def _expand_env_vars(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env_vars(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(val) for val in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return _expand_env_vars(data)


def load_settings(path: Path | None = None) -> dict:
    settings_path = path or (project_root() / "config" / "settings.yaml")
    return load_yaml(settings_path)


def load_profile(path: Path | None = None) -> dict:
    profile_path = path or (project_root() / "config" / "profile.yaml")
    return load_yaml(profile_path)
