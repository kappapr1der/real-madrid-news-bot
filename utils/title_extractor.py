import re
from html import unescape
from typing import Optional
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CoffeeBot/1.0; +https://t.me/slivochniyfootball)"
}

def _clean_title(t: str) -> str:
    t = unescape(t or "").strip()
    t = re.sub(r"\s+[-|]\s+(ESPN(?: FC)?|Sky Sports.*|Football España).*?$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s{2,}", " ", t)
    return t

def extract_title(url: str, timeout: float = 6.0) -> Optional[str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    for sel, attr in [
        ("meta[property='og:title']", "content"),
        ("meta[name='twitter:title']", "content"),
    ]:
        tag = soup.select_one(sel)
        if tag and tag.get(attr):
            return _clean_title(tag.get(attr))
    if soup.title and soup.title.text:
        return _clean_title(soup.title.text)
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return _clean_title(h1.get_text(strip=True))
    return None
