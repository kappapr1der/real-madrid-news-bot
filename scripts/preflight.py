#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "runtime_config.py",
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
    "tzdata": "tzdata",
}


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


def check_env():
    env_path = ROOT / ".env"
    if not env_path.exists():
        print("WARN .env not found; copy .env.example before live deployment")
    else:
        print("OK .env exists")


def main():
    check_syntax()
    check_dependencies()
    check_env()
    print("Preflight complete")


if __name__ == "__main__":
    main()
