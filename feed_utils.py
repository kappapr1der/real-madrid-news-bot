import logging
import subprocess
import time
from typing import Any
from urllib.parse import unquote, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from runtime_config import HTTP_USER_AGENT, RSS_TIMEOUT_SECONDS

HEADERS = {"User-Agent": HTTP_USER_AGENT}
_FEED_CACHE: dict[str, tuple[float, Any]] = {}


def normalize_x_media_url(url: str) -> str:
    """Prefer Twitter's image CDN when a Nitter image proxy is unavailable."""
    clean = (url or "").strip()
    parsed = urlparse(clean)
    marker = "/pic/"
    if not parsed.netloc or marker not in parsed.path:
        return clean
    raw_path = unquote(parsed.path.split(marker, 1)[1]).lstrip("/")
    if raw_path.startswith(("media/", "amplify_video_thumb/", "tweet_video_thumb/")):
        return f"https://pbs.twimg.com/{raw_path}"
    return clean


def source_is_x(source: str | dict) -> bool:
    return isinstance(source, dict) and str(source.get("kind", "")).startswith("x_")


def is_repost_entry(entry) -> bool:
    title = str(entry.get("title", "") or "").strip().casefold()
    return title.startswith("rt by @") or title.startswith("retweet by @")


def entry_media_url(entry) -> str:
    """Return the first usable image URL exposed by an RSS entry."""
    for key in ("media_content", "media_thumbnail", "enclosures"):
        rows = entry.get(key, []) or []
        if isinstance(rows, dict):
            rows = [rows]
        for row in rows:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or row.get("href") or "").strip()
            if url.startswith(("https://", "http://")) and not url.lower().endswith(".svg"):
                return normalize_x_media_url(url)

    summary = str(entry.get("summary", "") or "")
    if not summary:
        return ""
    soup = BeautifulSoup(summary, "html.parser")
    for image in soup.select("img[src]"):
        url = str(image.get("src") or "").strip()
        if url.startswith(("https://", "http://")) and not url.lower().endswith(".svg"):
            return normalize_x_media_url(url)
    return ""


def clear_feed_cache() -> None:
    _FEED_CACHE.clear()


def _feed_urls(source: str | dict) -> list[str]:
    if isinstance(source, str):
        return [source]

    urls = [str(source.get("url", "") or "")]
    fallback_urls = source.get("fallback_urls", [])
    if isinstance(fallback_urls, str):
        fallback_urls = [fallback_urls]
    urls.extend(str(url or "") for url in fallback_urls)

    unique: list[str] = []
    seen: set[str] = set()
    for url in urls:
        clean = url.strip()
        if clean and clean not in seen:
            unique.append(clean)
            seen.add(clean)
    return unique


def _cache_seconds(source: str | dict) -> int:
    if not isinstance(source, dict):
        return 0
    try:
        return max(int(source.get("cache_seconds", 0) or 0), 0)
    except (TypeError, ValueError):
        return 0


def _is_usable_feed(feed, source: str | dict) -> bool:
    entries = list(getattr(feed, "entries", []) or [])
    if not isinstance(source, dict) or not source.get("rss_require_entries"):
        return True
    if not entries:
        return False
    titles = [str(entry.get("title", "") or "").casefold() for entry in entries]
    return not titles or not all("rss reader not yet whitelisted" in title for title in titles)


def _fetch_feed_content(url: str, source: str | dict) -> bytes | None:
    use_curl = isinstance(source, dict) and source.get("rss_fetcher") == "curl"
    if use_curl:
        timeout = min(max(RSS_TIMEOUT_SECONDS, 1), 10)
        command = [
            "curl",
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--connect-timeout",
            str(min(timeout, 5)),
            "--max-time",
            str(timeout),
            "--user-agent",
            HTTP_USER_AGENT,
            url,
        ]
        try:
            result = subprocess.run(command, capture_output=True, check=False, timeout=timeout + 2)
        except (OSError, subprocess.TimeoutExpired) as exc:
            logging.warning("RSS curl request failed for %s: %s", url, exc)
            return None
        if result.returncode:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            logging.warning("RSS curl request failed for %s: %s", url, detail or result.returncode)
            return None
        return result.stdout

    try:
        response = requests.get(url, headers=HEADERS, timeout=RSS_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.warning("RSS request failed for %s: %s", url, exc)
        return None
    return response.content


def parse_feed_url(source: str | dict):
    """Fetch an RSS source, trying its configured mirror URLs in order."""
    urls = _feed_urls(source)
    if not urls:
        return None

    cache_seconds = _cache_seconds(source)
    cache_key = "\n".join(urls)
    cached = _FEED_CACHE.get(cache_key)
    if cached and cache_seconds and time.monotonic() - cached[0] < cache_seconds:
        return cached[1]

    for index, url in enumerate(urls):
        content = _fetch_feed_content(url, source)
        if content is None:
            continue

        feed = feedparser.parse(content)
        if getattr(feed, "bozo", False):
            logging.warning("RSS parsed with warning: %s", url)
        if not _is_usable_feed(feed, source):
            logging.warning("RSS mirror returned no usable entries: %s", url)
            continue

        if index:
            logging.info("RSS mirror recovered source via %s", url)
        if cache_seconds:
            _FEED_CACHE[cache_key] = (time.monotonic(), feed)
        return feed

    return None
