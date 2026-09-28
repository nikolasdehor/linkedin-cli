"""Config: flags > env > user config > defaults (XDG)."""

from __future__ import annotations

import os
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

if sys.version_info < (3, 11):  # tomllib guard, requires-python já exige 3.11
    raise RuntimeError("linkedin requer Python 3.11+")

DEFAULT_TIMEOUT = 180.0
MOTOR_CANDIDATES = ("linkedin-scraper-mcp", "mcp-server-linkedin")


@dataclass
class Settings:
    motor: str | None = None
    timeout: float = DEFAULT_TIMEOUT
    output: str = "human"  # human | json | plain


def user_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(base) / "linkedin" / "config.toml"


def load_file_settings(path: Path | None = None) -> Settings:
    s = Settings()
    cfg = path or user_config_path()
    try:
        raw = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return s
    except (OSError, tomllib.TOMLDecodeError):
        return s
    if not isinstance(raw, dict):
        return s
    if isinstance(raw.get("motor"), str):
        s.motor = raw["motor"]
    try:
        s.timeout = float(raw.get("timeout", s.timeout))
    except (TypeError, ValueError):
        pass
    if raw.get("output") in ("human", "json", "plain"):
        s.output = raw["output"]
    return s


def apply_env(s: Settings) -> Settings:
    if os.environ.get("LINKEDIN_MOTOR"):
        s.motor = os.environ["LINKEDIN_MOTOR"]
    try:
        if os.environ.get("LINKEDIN_TIMEOUT"):
            s.timeout = float(os.environ["LINKEDIN_TIMEOUT"])
    except ValueError:
        pass
    if os.environ.get("LINKEDIN_OUTPUT") in ("human", "json", "plain"):
        s.output = os.environ["LINKEDIN_OUTPUT"]
    return s


def find_motor(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    s = apply_env(load_file_settings())
    if s.motor:
        return s.motor
    for name in MOTOR_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


def colors_allowed(no_color_flag: bool) -> bool:
    if no_color_flag or os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()
