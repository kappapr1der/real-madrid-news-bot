#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import os
import re
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "runtime_config.py",
    "feed_utils.py",
    "post_utils.py",
    "status_manager.py",
    "content_quality.py",
    "live_providers.py",
    "match_calendar.py",
    "matchday.py",
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
HASHTAG_CONFIG_NAMES = (
    "POST_HASHTAGS",
    "DIGEST_HASHTAGS",
    "BREAKING_HASHTAGS",
    "MATCHDAY_HASHTAGS",
    "LIVE_HASHTAGS",
)


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


def validate_int_list(config: dict, name: str, default: str, errors: list[str]) -> None:
    raw = (config.get(name) or default).strip()
    if not raw:
        errors.append(f"{name} must contain at least one integer id")
        return

    for part in raw.replace(";", ",").split(","):
        value = part.strip()
        if not value:
            continue
        try:
            int(value)
        except ValueError:
            errors.append(f"{name} must be a comma-separated list of integer ids")
            return


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def check_state_writable(config: dict, errors: list[str]) -> None:
    state_dir = resolve_repo_path(config.get("STATE_DIR") or "state")
    if not state_dir.exists():
        return
    if not os.access(state_dir, os.W_OK | os.X_OK):
        errors.append(f"STATE_DIR is not writable by the effective user: {state_dir}")
        return

    for path in sorted(state_dir.rglob("*")):
        if path.is_file() and not os.access(path, os.W_OK):
            errors.append(f"state file is not writable by the effective user: {path}")


def check_env():
    from dotenv import dotenv_values

    env_path = ROOT / ".env"
    if not env_path.exists():
        print("WARN .env not found; copy .env.example before live deployment")
        return

    config = dotenv_values(env_path)
    errors: list[str] = []
    warnings: list[str] = []

    bool_rules = {
        "DRY_RUN": "true",
        "DIGEST_INCLUDE_UNDATED": "false",
        "DIGEST_DEDUPE_ENABLED": "true",
        "DIGEST_PRIORITY_SORT_ENABLED": "true",
        "DIGEST_SHOW_RELATED_SOURCES": "true",
        "MATCHDAY_ENABLED": "true",
        "MATCHDAY_BLOCK_ALL_DAY": "false",
        "MATCHDAY_LIVE_ENABLED": "false",
        "YANDEX_LLM_ENABLED": "false",
        "LLM_EDITOR_DIGEST_ENABLED": "true",
        "LLM_EDITOR_BREAKING_ENABLED": "true",
    }
    for name, default in bool_rules.items():
        raw = (config.get(name) or default).strip().lower()
        if raw not in BOOL_VALUES:
            errors.append(f"{name} must be true or false")

    dry_run = env_bool_value(config, "DRY_RUN", "true")

    if not dry_run:
        if is_placeholder(config.get("TELEGRAM_BOT_TOKEN")):
            errors.append("TELEGRAM_BOT_TOKEN is required for DRY_RUN=false")
        if is_placeholder(config.get("TARGET_CHAT_ID")):
            errors.append("TARGET_CHAT_ID is required for DRY_RUN=false")

    heartbeat_host = (config.get("HEARTBEAT_HOST") or "127.0.0.1").strip()
    heartbeat_token = (config.get("HEARTBEAT_TOKEN") or "").strip()
    if heartbeat_host in {"0.0.0.0", "::"} and not heartbeat_token:
        warnings.append("HEARTBEAT_TOKEN is recommended when HEARTBEAT_HOST is public")

    for name in HASHTAG_CONFIG_NAMES:
        if name in config and not (config.get(name) or "").strip():
            warnings.append(f"{name} is empty; quote values that start with #")

    for name in ("DIGEST_MORNING_TIME", "DIGEST_DAY_TIME", "DIGEST_EVENING_TIME"):
        value = (config.get(name) or "").strip()
        if value and not TIME_RE.match(value):
            errors.append(f"{name} must use HH:MM 24-hour format")

    int_rules = {
        "BREAKING_INTERVAL_SECONDS": ("120", 30),
        "HEARTBEAT_PORT": ("8000", 1),
        "HEARTBEAT_MAIN_STALE_SECONDS": ("180", 30),
        "HEARTBEAT_BREAKING_STALE_SECONDS": ("420", 60),
        "HEARTBEAT_MATCHDAY_STALE_SECONDS": ("600", 60),
        "HEARTBEAT_LIVE_STALE_SECONDS": ("900", 60),
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
        "DIGEST_DEDUPE_SIMILARITY": ("42", 0),
        "MATCHDAY_BLOCK_BEFORE_HOURS": ("3", 0),
        "MATCHDAY_BLOCK_AFTER_HOURS": ("2", 0),
        "MATCHDAY_PREVIEW_MINUTES": ("60", 0),
        "MATCHDAY_HALFTIME_MINUTES": ("50", 1),
        "MATCHDAY_FULLTIME_MINUTES": ("125", 1),
        "MATCHDAY_POST_TOLERANCE_MINUTES": ("20", 1),
        "MATCHDAY_POLL_SECONDS": ("60", 10),
        "MATCHDAY_LIVE_POLL_SECONDS": ("180", 60),
        "MATCHDAY_LIVE_BEFORE_MINUTES": ("15", 0),
        "MATCHDAY_LIVE_AFTER_MINUTES": ("30", 0),
        "API_FOOTBALL_TEAM_ID": ("541", 1),
        "API_FOOTBALL_REQUEST_TIMEOUT_SECONDS": ("10", 1),
        "YANDEX_LLM_TIMEOUT_SECONDS": ("20", 1),
        "YANDEX_LLM_MAX_TOKENS": ("900", 1),
        "LLM_EDITOR_DAILY_REQUEST_LIMIT": ("60", 1),
        "LLM_EDITOR_DAILY_CHAR_LIMIT": ("150000", 1000),
        "LLM_EDITOR_MAX_DIGEST_ITEMS": ("14", 1),
        "LLM_EDITOR_MAX_BREAKING_ITEMS": ("10", 1),
        "LLM_EDITOR_MAX_SUMMARY_CHARS": ("240", 80),
        "LLM_EDITOR_BREAKING_BUFFER_SECONDS": ("600", 0),
        "LLM_EDITOR_BREAKING_MIN_INTERVAL_SECONDS": ("600", 0),
        "LLM_EDITOR_BREAKING_FALLBACK_AFTER_SECONDS": ("3600", 0),
    }
    parsed_values = {}
    for name, (default, minimum) in int_rules.items():
        parsed_values[name] = validate_int(config, name, default, minimum, errors)

    message_limit = parsed_values.get("TELEGRAM_MESSAGE_LIMIT")
    if message_limit is not None and message_limit > 4096:
        errors.append("TELEGRAM_MESSAGE_LIMIT must be <= 4096")

    dedupe_similarity = parsed_values.get("DIGEST_DEDUPE_SIMILARITY")
    if dedupe_similarity is not None and dedupe_similarity > 100:
        errors.append("DIGEST_DEDUPE_SIMILARITY must be <= 100")

    matchday_enabled = env_bool_value(config, "MATCHDAY_ENABLED", "true")
    schedule_file = resolve_repo_path(config.get("MATCH_SCHEDULE_FILE") or "config/matches.json")
    if matchday_enabled and not schedule_file.exists():
        warnings.append(f"MATCH_SCHEDULE_FILE not found: {schedule_file}")

    validate_int_list(config, "API_FOOTBALL_LEAGUE_IDS", "140,2", errors)
    live_enabled = env_bool_value(config, "MATCHDAY_LIVE_ENABLED", "false")
    live_provider = (config.get("MATCHDAY_LIVE_PROVIDER") or "api-football").strip().lower()
    live_key = config.get("API_FOOTBALL_KEY") or config.get("APISPORTS_KEY")
    if live_provider != "api-football":
        errors.append("MATCHDAY_LIVE_PROVIDER currently supports only api-football")
    if live_enabled and is_placeholder(live_key):
        errors.append("API_FOOTBALL_KEY or APISPORTS_KEY is required for MATCHDAY_LIVE_ENABLED=true")
    if live_enabled and not (config.get("MATCHDAY_LIVE_EVENT_TYPES") or "").strip():
        warnings.append("MATCHDAY_LIVE_EVENT_TYPES is empty; all provider event types will be accepted")

    llm_enabled = env_bool_value(config, "YANDEX_LLM_ENABLED", "false")
    llm_key = config.get("YANDEX_LLM_API_KEY") or config.get("YANDEX_TRANSLATE_API_KEY") or config.get("YANDEX_API_KEY")
    llm_folder = config.get("YANDEX_LLM_FOLDER_ID") or config.get("YANDEX_FOLDER_ID")
    if llm_enabled and not llm_key:
        errors.append("YANDEX_LLM_API_KEY, YANDEX_TRANSLATE_API_KEY or YANDEX_API_KEY is required for YANDEX_LLM_ENABLED=true")
    if llm_enabled and not llm_folder:
        errors.append("YANDEX_LLM_FOLDER_ID or YANDEX_FOLDER_ID is required for YANDEX_LLM_ENABLED=true")

    check_state_writable(config, errors)

    if errors:
        joined = "\n- ".join(errors)
        raise RuntimeError(f"Env validation failed:\n- {joined}")

    for warning in warnings:
        print(f"WARN {warning}")

    mode = "DRY_RUN" if dry_run else "LIVE"
    print(f"OK .env exists ({mode})")


def main():
    check_syntax()
    check_dependencies()
    check_env()
    print("Preflight complete")


if __name__ == "__main__":
    main()
