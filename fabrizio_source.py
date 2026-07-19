"""Read fresh posts from Fabrizio Romano's official public Telegram channel."""

from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

from runtime_config import HTTP_USER_AGENT, RSS_TIMEOUT_SECONDS


HEADERS = {"User-Agent": HTTP_USER_AGENT}


def parse_fabrizio_telegram_html(html: str) -> list[dict[str, Any]]:
    """Turn Telegram's public channel page into a small, newest-first entry list."""
    soup = BeautifulSoup(html, "html.parser")
    entries: list[dict[str, Any]] = []

    for message in soup.select(".tgme_widget_message"):
        body = message.select_one(".tgme_widget_message_text")
        date = message.select_one("time[datetime]")
        link = message.select_one(".tgme_widget_message_date[href]")
        if not body or not date or not link:
            continue

        text = body.get_text(" ", strip=True)
        href = str(link.get("href") or "").strip()
        raw_time = str(date.get("datetime") or "").strip()
        if not text or not href or not raw_time:
            continue

        try:
            published_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            continue

        entries.append(
            {
                "title": text,
                "summary": "",
                "link": href,
                "published_at": published_at,
            }
        )

    return sorted(entries, key=lambda entry: entry["published_at"], reverse=True)


def fetch_fabrizio_telegram_entries(url: str) -> list[dict[str, Any]]:
    response = requests.get(url, headers=HEADERS, timeout=RSS_TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_fabrizio_telegram_html(response.text)
