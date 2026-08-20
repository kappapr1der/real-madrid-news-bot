from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from runtime_config import HTTP_USER_AGENT, RSS_TIMEOUT_SECONDS

HEADERS = {"User-Agent": HTTP_USER_AGENT}
IMAGE_META_SELECTORS = (
    ("property", "og:image"),
    ("property", "og:image:secure_url"),
    ("name", "twitter:image"),
    ("name", "twitter:image:src"),
)


def normalize_image_url(page_url: str, image_url: str) -> str:
    return urljoin(page_url, image_url.strip())


def fetch_article_image(url: str) -> str | None:
    if not url:
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=RSS_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    for attr, value in IMAGE_META_SELECTORS:
        tag = soup.find("meta", attrs={attr: value})
        content = tag.get("content") if tag else ""
        if not content:
            continue
        image_url = normalize_image_url(url, content)
        if image_url.startswith(("http://", "https://")) and not image_url.lower().endswith(".svg"):
            return image_url
    return None
