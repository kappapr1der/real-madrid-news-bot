#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

import feedparser
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sources_international import SOURCES_INTERNATIONAL  # noqa: E402
from sources_ru import SOURCES_RU  # noqa: E402

HEADERS = {
    "User-Agent": "CoffeeBot/1.0 (+https://github.com/kappapr1der/real-madrid-news-bot)",
}
TIMEOUT_SECONDS = 15


def check_source(source):
    label = source.get("label", "Unknown")
    url = source.get("url")
    if not url:
        return "FAIL", label, "missing URL"

    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        return "FAIL", label, f"HTTP error: {exc}"

    feed = feedparser.parse(response.content)
    entries = len(feed.entries or [])
    if entries == 0:
        return "WARN", label, f"no entries: {url}"

    bozo = " bozo" if getattr(feed, "bozo", False) else ""
    return "OK", label, f"{entries} entries{bozo}: {url}"


def main():
    sources = SOURCES_INTERNATIONAL + SOURCES_RU
    failed = 0
    warned = 0

    for source in sources:
        status, label, detail = check_source(source)
        print(f"{status:4} {label}: {detail}")
        if status == "FAIL":
            failed += 1
        elif status == "WARN":
            warned += 1

    print(f"Checked {len(sources)} sources: {failed} failed, {warned} warnings")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
