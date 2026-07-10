from runtime_config import X_RSS_BASE_URL, X_RSS_HANDLES


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


def _x_rss_url(handle: str) -> str:
    template = X_RSS_BASE_URL.rstrip("/")
    if "{handle}" in template:
        return template.format(handle=handle)
    return f"{template}/{handle}"


def build_x_sources() -> list[dict]:
    if not X_RSS_BASE_URL:
        return []
    sources = []
    for handle in X_RSS_HANDLES:
        clean = handle.strip().lstrip("@")
        if not clean:
            continue
        normalized = clean.casefold()
        trust = "official" if normalized in X_OFFICIAL_HANDLES else "reporter" if normalized in X_REPORTER_HANDLES else "community"
        sources.append(
            {
                "url": _x_rss_url(clean),
                "label": f"X – @{clean}",
                "kind": f"x_{trust}",
                "trust": trust,
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

SOURCES_INTERNATIONAL = REAL_MADRID_SOURCES + GENERAL_FOOTBALL_SOURCES + X_SOURCES
