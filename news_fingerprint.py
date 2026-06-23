import re
import unicodedata
from pathlib import Path


STOPWORDS = {
    "a", "an", "and", "as", "at", "for", "from", "in", "is", "it", "of", "on", "or", "the",
    "to", "with", "about", "after", "amid", "before", "into", "over", "while",
    "real", "madrid", "реал", "мадрид", "мадридский", "мадридского", "мадридском",
    "official", "oficial", "confirmado", "confirmed", "report", "reports",
    "официально", "подтверждено", "сообщает", "заявление", "коммюнике",
}


PLAYER_ALIASES = {
    "julian-alvarez": ("julian alvarez", "julián álvarez", "хулиан альварес", "хулиана альвареса"),
    "rodri": ("rodri", "родри"),
    "olise": ("olise", "олисе", "michael olise", "майкл олисе", "михаэль олисе"),
    "enzo-fernandez": ("enzo fernandez", "enzo fernández", "энцо фернандес"),
    "bernardo-silva": ("bernardo silva", "бернардо сильва"),
    "felicia-schroder": ("felicia schroder", "felicia schröder", "фелисия шредер", "фелиция шредер"),
}


def normalize_news_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    replacements = {
        "ё": "е",
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
        "–": "-",
        "—": "-",
        "«": " ",
        "»": " ",
        "“": " ",
        "”": " ",
        "'": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-zа-я0-9#€$]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def player_key(text: str) -> str | None:
    for key, aliases in PLAYER_ALIASES.items():
        if any(alias in text for alias in aliases):
            return key
    return None


def semantic_news_key(title: str, summary: str = "") -> str:
    text = normalize_news_text(f"{title} {summary}")

    if (
        contains_any(text, ("cvc", "tebas", "тебас", "audiovisual", "audiovisuales", "аудиовизуаль"))
        and contains_any(text, ("laliga", "la liga", "лига", "лиги", "rights", "derechos", "права", "прав"))
    ):
        return "legal:laliga-cvc-rights"

    player = player_key(text)
    if player and contains_any(text, ("no fichara", "no firmara", "no sign", "not sign", "не подпиш", "не перейдет")):
        return f"transfer:no-sign:{player}"

    if player and contains_any(text, ("fichaje", "transfer", "signing", "подпис", "трансфер", "переход")):
        return f"transfer:rumour:{player}"

    if contains_any(text, ("femenino", "femenina", "женск", "фелисия шредер", "фелиция шредер")):
        return "women:real-madrid"

    tokens = [
        token
        for token in text.split()
        if len(token) > 2 and token not in STOPWORDS and not token.isdigit()
    ]
    return "generic:" + "-".join(tokens[:10])


def load_news_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    except OSError:
        return set()


def save_news_keys(path: Path, keys: set[str]) -> None:
    path.write_text("\n".join(sorted(keys)) + ("\n" if keys else ""), encoding="utf-8")
