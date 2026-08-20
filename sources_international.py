from runtime_config import (
    HERE_WE_GO_ENABLED,
    HERE_WE_GO_TELEGRAM_URL,
    X_NITTER_INSTANCES,
    X_RSS_BASE_URL,
    X_RSS_BREAKING_ENTRY_SCAN_LIMIT,
    X_RSS_CACHE_SECONDS,
    X_RSS_HANDLES,
)


X_OFFICIAL_HANDLES = {"realmadrid", "realmadriden"}
X_REPORTER_HANDLES = {
    "mariocortegana",
    "aranchamobile",
    "melchorcope",
    "jlsanchez78",
    "ramon_alvarezmm",
    "guillermorai_",
    "fabrizioromano",
}


def _x_rss_url(template: str, handle: str) -> str:
    template = template.rstrip("/")
    if "{handle}" in template:
        return template.format(handle=handle)
    return f"{template}/{handle}"


def _nitter_rss_url(instance: str, handle: str) -> str:
    return f"{instance.rstrip('/')}/{handle}/rss"


def _dedupe_urls(urls: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for url in urls:
        clean = url.strip()
        if clean and clean not in seen:
            unique.append(clean)
            seen.add(clean)
    return unique


def build_x_sources() -> list[dict]:
    if not X_RSS_BASE_URL and not X_NITTER_INSTANCES:
        return []
    sources = []
    for handle in X_RSS_HANDLES:
        clean = handle.strip().lstrip("@")
        if not clean:
            continue
        urls = []
        if X_RSS_BASE_URL:
            urls.append(_x_rss_url(X_RSS_BASE_URL, clean))
        urls.extend(_nitter_rss_url(instance, clean) for instance in X_NITTER_INSTANCES)
        urls = _dedupe_urls(urls)
        if not urls:
            continue
        normalized = clean.casefold()
        trust = "official" if normalized in X_OFFICIAL_HANDLES else "reporter" if normalized in X_REPORTER_HANDLES else "community"
        sources.append(
            {
                "url": urls[0],
                "fallback_urls": urls[1:],
                "label": f"X – @{clean}",
                "kind": f"x_{trust}",
                "trust": trust,
                "cache_seconds": X_RSS_CACHE_SECONDS,
                "rss_require_entries": True,
                "rss_fetcher": "curl",
                "breaking_entry_scan_limit": X_RSS_BREAKING_ENTRY_SCAN_LIMIT,
            }
        )
    return sources


REAL_MADRID_SOURCES = [
    {"url": "https://www.managingmadrid.com/rss/index.xml", "label": "Managing Madrid"},
    {"url": "https://madriduniversal.com/feed/", "label": "Madrid Universal"},
    {"url": "https://therealchamps.com/feed/", "label": "The Real Champs"},
    {"url": "https://www.realmadridnews.com/feed", "label": "Real Madrid News"},
    {"url": "https://www.football-espana.net/category/la-liga/real-madrid/feed", "label": "Football España – Real Madrid"},
    {"url": "https://www.marca.com/rss/futbol/real-madrid.xml", "label": "Marca – Real Madrid"},
    {"url": "https://defensacentral.com/uploads/feeds/feed_defensa-central_es.xml", "label": "Defensa Central"},
    {"url": "https://www.bernabeudigital.com/rss", "label": "Bernabéu Digital"},
    {"url": "https://www.mundodeportivo.com/feed/rss/futbol/real-madrid", "label": "Mundo Deportivo – Real Madrid"},
    {"url": "https://www.sport.es/es/rss/real-madrid/rss.xml", "label": "Sport – Real Madrid"},
    {"url": "https://www.caughtoffside.com/tags/real-madrid/feed/", "label": "CaughtOffside – Real Madrid"},
]

GENERAL_FOOTBALL_SOURCES = [
    {"url": "https://www.espn.com/espn/rss/soccer/news", "label": "ESPN FC"},
    {"url": "https://www.skysports.com/rss/12040", "label": "Sky Sports Football"},
    {"url": "https://www.football-espana.net/feed", "label": "Football España"},
    {"url": "https://feeds.bbci.co.uk/sport/football/rss.xml", "label": "BBC Sport Football"},
    {"url": "https://www.theguardian.com/football/rss", "label": "Guardian Football"},
    {"url": "https://www.independent.co.uk/sport/football/rss", "label": "Independent Football"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Soccer.xml", "label": "NY Times Soccer"},
    {"url": "https://www.fourfourtwo.com/feeds/all", "label": "FourFourTwo"},
    {"url": "https://www.90min.com/posts.rss", "label": "90min"},
    {"url": "https://www.cbssports.com/rss/headlines/soccer/", "label": "CBS Soccer"},
]

X_SOURCES = build_x_sources()

HERE_WE_GO_SOURCES = (
    [
        {
            "url": HERE_WE_GO_TELEGRAM_URL,
            "label": "Fabrizio Romano - Telegram",
            "kind": "fabrizio_telegram",
            "trust": "reporter",
        }
    ]
    if HERE_WE_GO_ENABLED and HERE_WE_GO_TELEGRAM_URL
    else []
)

SOURCES_INTERNATIONAL = REAL_MADRID_SOURCES + GENERAL_FOOTBALL_SOURCES + X_SOURCES
