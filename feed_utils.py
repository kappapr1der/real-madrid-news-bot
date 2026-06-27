import logging

import feedparser
import requests

from runtime_config import HTTP_USER_AGENT, RSS_TIMEOUT_SECONDS

HEADERS = {"User-Agent": HTTP_USER_AGENT}


def parse_feed_url(url: str):
    try:
        response = requests.get(url, headers=HEADERS, timeout=RSS_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("Ошибка HTTP при чтении RSS %s: %s", url, exc)
        return None

    feed = feedparser.parse(response.content)
    if getattr(feed, "bozo", False):
        logging.warning("RSS разобран с предупреждением: %s", url)
    return feed
