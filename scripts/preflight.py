#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import re
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "runtime_config.py",
    "feed_utils.py",
    "main.py",
    "heartbeat.py",
    "breaking.py",
    "digest.py",
    "filters.py",
    "text_cleaner.py",
    "translator.py",
    "sources_international.py",
    "sources_ru.py",
    "uptime_webhook.py",
    "scripts/check_sources.py",
]

REQUIRED_MODULES = {
    "requests": "requests",
    "feedparser": "feedparser",
    "dotenv": "python-dotenv",
    "deep_translator": "deep-translator",
    "colorama": "colorama",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "flask": "Flask",
    "schedule": "schedule",
    "pytz": "pytz",
    "tzdata": "tzdata",
}

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
BOOL_VALUES = {"1", "true", "yes", "y", "on", "0", "false", "no", "n", "off"}


def check_syntax():
    for relative in FILES:
        path = ROOT / relative
        if not path.exists():
            raise FileNotFoundError(f"Missing expected file: {relative}")
        py_compile.compile(str(path), doraise=True)
        print(f"OK syntax {relative}")


def check_dependencies():
    missing = []
    for module_name, package_name in REQUIRED_MODULES.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
        else:
            print(f"OK dependency {package_name}")

    if missing:
        names = ", ".join(sorted(missing))
        raise RuntimeError(f"Missing dependencies: {names}. Run: pip install -r requirements.txt")


def is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.lower()
    return "replace_me" in lowered or value.startswith("123456789:") or value == "@your_channel_username"


def env_bool_value(config: dict, name: str, default: str) -> bool:
    raw = (config.get(name) or default).strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def parse_int(config: dict, name: str, default: str, errors: list[str]) -> int | None:
    raw = (config.get(name) or default).strip()
    try:
        return int(raw)
    except ValueError:
        errors.append(f"{name} must be an integer")
        return None


def validate_int(config: dict, name: str, default: str, minimum: int, errors: list[str]) -> int | None:
    value = parse_int(config, name, default, errors)
    if value is None:
        return None
    if value < minimum:
        errors.append(f"{name} must be >= {minimum}")
    return value


def check_env():
    from dotenv import dotenv_values

    env_path = ROOT / ".env"
    if not env_path.exists():
        print("WARN .env not found; copy .env.example before live deployment")
        return

    config = dotenv_values(env_path)
    errors: list[str] = []

    raw_dry_run = (config.get("DRY_RUN") or "true").strip().lower()
    if raw_dry_run not in BOOL_VALUES:
        errors.append("DRY_RUN must be true or false")
    dry_run = env_bool_value(config, "DRY_RUN", "true")

    if not dry_run:
        if is_placeholder(config.get("TELEGRAM_BOT_TOKEN")):
            errors.append("TELEGRAM_BOT_TOKEN is required for DRY_RUN=false")
        if is_placeholder(config.get("TARGET_CHAT_ID")):
            errors.append("TARGET_CHAT_ID is required for DRY_RUN=false")

    for name in ("DIGEST_MORNING_TIME", "DIGEST_DAY_TIME", "DIGEST_EVENING_TIME"):
        value = (config.get(name) or "").strip()
        if value and not TIME_RE.match(value):
            errors.append(f"{name} must use HH:MM 24-hour format")

    int_rules = {
        "BREAKING_INTERVAL_SECONDS": ("120", 30),
        "HEARTBEAT_PORT": ("8000", 1),
        "RSS_TIMEOUT_SECONDS": ("15", 1),
        "TELEGRAM_TIMEOUT_SECONDS": ("10", 1),
        "TELEGRAM_MESSAGE_LIMIT": ("3900", 1000),
        "DIGEST_LIMIT": ("10", 1),
        "DIGEST_ENTRY_SCAN_LIMIT": ("5", 1),
        "DIGEST_DEFAULT_LOOKBACK_HOURS": ("8", 1),
        "DIGEST_MORNING_LOOKBACK_HOURS": ("14", 1),
        "DIGEST_DAY_LOOKBACK_HOURS": ("8", 1),
        "DIGEST_EVENING_LOOKBACK_HOURS": ("8", 1),
        "DIGEST_NIGHT_LOOKBACK_HOURS": ("8", 1),
    }
    parsed_values = {}
    for name, (default, minimum) in int_rules.items():
        parsed_values[name] = validate_int(config, name, default, minimum, errors)

    message_limit = parsed_values.get("TELEGRAM_MESSAGE_LIMIT")
    if message_limit is not None and message_limit > 4096:
        errors.append("TELEGRAM_MESSAGE_LIMIT must be <= 4096")

    if errors:
        joined = "\n- ".join(errors)
        raise RuntimeError(f"Env validation failed:\n- {joined}")

    mode = "DRY_RUN" if dry_run else "LIVE"
    print(f"OK .env exists ({mode})")


def main():
    check_syntax()
    check_dependencies()
    check_env()
    print("Preflight complete")


if __name__ == "__main__":
    main()
