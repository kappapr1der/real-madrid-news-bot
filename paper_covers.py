from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import requests
from bs4 import BeautifulSoup

from runtime_config import HTTP_USER_AGENT, RSS_TIMEOUT_SECONDS


HEADERS = {"User-Agent": HTTP_USER_AGENT}
SPANISH_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


@dataclass(frozen=True)
class PaperCover:
    source_name: str
    page_url: str
    image_url: str


def _full_size_image_url(url: str) -> str:
    return url.replace("width=375", "width=1200")


def as_cover_archive_url(today: date | None = None) -> str:
    current = today or date.today()
    month = SPANISH_MONTHS[current.month - 1]
    return f"https://as.com/masdeporte/fotorrelato/las-portadas-de-as-de-{month}-f{current:%Y%m}-f/"


def fetch_latest_as_cover(url: str | None = None) -> PaperCover | None:
    """Return the first image from AS's newest-first monthly front-page gallery."""
    url = url or as_cover_archive_url()
    try:
        response = requests.get(url, headers=HEADERS, timeout=RSS_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    for image in soup.find_all("img"):
        image_url = str(image.get("src") or "").strip()
        if "img.asmedia.epimg.net/resizer/v2/" not in image_url:
            continue
        if "width=375" not in image_url:
            continue
        return PaperCover("Diario AS", url, _full_size_image_url(image_url))
    return None
