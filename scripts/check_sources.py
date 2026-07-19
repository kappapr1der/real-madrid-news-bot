#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feed_utils import parse_feed_url  # noqa: E402
from sources_international import SOURCES_INTERNATIONAL  # noqa: E402
from sources_ru import SOURCES_RU  # noqa: E402


def check_source(source):
    label = source.get("label", "Unknown")
    url = source.get("url")
    if not url:
        return "FAIL", label, "missing URL"

    feed = parse_feed_url(source)
    if not feed:
        return "FAIL", label, f"could not fetch RSS: {url}"

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
