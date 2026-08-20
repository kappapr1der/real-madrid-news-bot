"""Shared registry for editorial links that must not return in a digest."""

from __future__ import annotations

import json

from runtime_config import get_state_file


EDITORIAL_LINKS_FILE = get_state_file("editorial_sent_links.json")
MAX_LINKS = 600


def published_editorial_links() -> set[str]:
    if not EDITORIAL_LINKS_FILE.exists():
        return set()
    try:
        values = json.loads(EDITORIAL_LINKS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(value).strip() for value in values if str(value).strip()} if isinstance(values, list) else set()


def remember_editorial_link(link: str) -> None:
    clean = (link or "").strip()
    if not clean:
        return
    values = published_editorial_links()
    values.add(clean)
    EDITORIAL_LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    EDITORIAL_LINKS_FILE.write_text(
        json.dumps(sorted(values)[-MAX_LINKS:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
