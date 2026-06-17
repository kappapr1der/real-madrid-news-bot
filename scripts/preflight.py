#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
]


def main():
    for relative in FILES:
        path = ROOT / relative
        if not path.exists():
            raise FileNotFoundError(f"Missing expected file: {relative}")
        py_compile.compile(str(path), doraise=True)
        print(f"OK {relative}")

    env_path = ROOT / ".env"
    if not env_path.exists():
        print("WARN .env not found; copy .env.example before live deployment")

    print("Preflight complete")


if __name__ == "__main__":
    main()
