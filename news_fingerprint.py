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
    "nico-paz": ("nico paz", "paz", "нико пас"),
    "ceballos": ("ceballos", "себальос"),
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


def is_venezuela_donation_text(text: str) -> bool:
    return contains_any(text, ("venezuela", "venezuel", "венесуэл")) and contains_any(
        text,
        (
            "donate",
            "donation",
            "donan",
            "donar",
            "dona",
            "donacion",
            "solidaria",
            "solidarity",
            "millon",
            "million",
            "пожертв",
            "землетр",
        ),
    )


def is_joan_martinez_valencia_text(text: str) -> bool:
    return (
        contains_any(text, ("joan mart", "жоан март"))
        and contains_any(text, ("valencia", "валенси"))
        and contains_any(
            text,
            (
                "loan",
                "cesion",
                "cedido",
                "ceder",
                "pregunta",
                "interes",
                "interesa",
                "interest",
                "аренд",
                "интерес",
            ),
        )
    )


def is_laliga_rfef_meeting_text(text: str) -> bool:
    return (
        contains_any(text, ("laliga", "la liga", "rfef", "federacion", "federation", "лига", "rfe"))
        and contains_any(text, ("meeting", "summit", "reunion", "reunion", "asamblea", "sede", "clubs", "clubes", "собрани", "встреч"))
        and contains_any(text, ("skip", "miss", "absent", "no asist", "no acud", "no estara", "no estará", "пропуска", "не приед", "не поед"))
    )


def is_olise_bayern_talks_text(text: str) -> bool:
    return (
        contains_any(text, ("olise", "олисе", "galactico", "галактико", "hainer", "ahorrarse esfuerzo", "save effort", "сэкономить усилия"))
        and contains_any(text, ("bayern", "бавари"))
        and contains_any(
            text,
            (
                "talk",
                "negotiat",
                "conversation",
                "future",
                "situation",
                "monitor",
                "speculation",
                "conversacion",
                "conversaciones",
                "reunion",
                "futuro",
                "переговор",
                "будущ",
                "ситуац",
                "следит",
                "effort",
                "esfuerzo",
                "усили",
            ),
        )
    )


def is_asencio_loan_buy_text(text: str) -> bool:
    return (
        contains_any(text, ("asencio", "асенсио"))
        and contains_any(text, ("loan", "cesion", "cedido", "аренд"))
        and contains_any(text, ("buy", "mandatory", "oblig", "compra", "выкуп"))
    )


def is_nico_paz_como_text(text: str) -> bool:
    return (
        contains_any(text, ("nico paz", "нико пас", "paz"))
        and contains_any(text, ("como", "комо"))
        and contains_any(
            text,
            (
                "queda",
                "quedara",
                "quedará",
                "stays",
                "stay",
                "continua",
                "continúa",
                "seguira",
                "seguirá",
                "deja",
                "leaves",
                "sale",
                "salida",
                "traspaso",
                "transfer",
                "покидает",
                "остается",
                "останется",
                "переходит",
                "переход",
            ),
        )
    )


def is_laporta_attacks_real_text(text: str) -> bool:
    return (
        contains_any(text, ("laporta", "лапорта"))
        and contains_any(text, ("real madrid", "florentino", "реал", "флорентино"))
        and contains_any(
            text,
            (
                "attacks",
                "takes aim",
                "critica",
                "critico",
                "critic",
                "ataca",
                "deja vu",
                "критик",
                "атак",
            ),
        )
    )


def semantic_news_key(title: str, summary: str = "") -> str:
    text = normalize_news_text(f"{title} {summary}")

    if is_nico_paz_como_text(text):
        return "transfer:nico-paz-como"

    if is_laporta_attacks_real_text(text):
        return "barca:laporta-attacks-real"

    if is_venezuela_donation_text(text):
        return "club:donation:venezuela-earthquake"

    if is_joan_martinez_valencia_text(text):
        return "transfer:loan:joan-martinez-valencia"

    if is_laliga_rfef_meeting_text(text):
        return "club:laliga-rfef-meeting-skip"

    if is_olise_bayern_talks_text(text):
        return "transfer:olise-bayern-talks-real-monitoring"

    if is_asencio_loan_buy_text(text):
        return "transfer:loan:asencio-mandatory-buy"

    if (
        contains_any(text, ("cvc", "tebas", "тебас", "audiovisual", "audiovisuales", "аудиовизуаль"))
        and contains_any(text, ("laliga", "la liga", "лига", "лиги", "rights", "derechos", "права", "прав"))
    ):
        return "legal:laliga-cvc-rights"

    if contains_any(text, ("manuel arroyo", "doctor", "medico", "medico primer equipo")) and contains_any(
        text,
        ("resigns", "resign", "dimite", "dimision", "renuncia", "real madrid"),
    ):
        return "staff:doctor-resigns:manuel-arroyo"

    if contains_any(text, ("academy goalkeeper", "cantera goalkeeper", "goalkeeper wanted")) and contains_any(
        text,
        ("la liga clubs", "several la liga", "primera"),
    ):
        return "academy:fran-gonzalez-la-liga-interest"

    if contains_any(text, ("fran gonzalez", "fran")) and contains_any(
        text,
        ("goalkeeper", "portero", "meta", "castilla", "academy"),
    ) and contains_any(text, ("wanted", "luchan", "clubes", "clubs", "primera", "la liga", "laliga")):
        return "academy:fran-gonzalez-la-liga-interest"

    player = player_key(text)
    if player and contains_any(text, ("no fichara", "no firmara", "no sign", "not sign", "не подпиш", "не перейдет")):
        return f"transfer:no-sign:{player}"

    departure_terms = (
        "salida", "se marcha", "marcha", "leave", "leaves", "exit", "departure", "farewell", "despedida",
        "rescinde", "rescind", "termination", "mutual agreement", "mutuo acuerdo",
        "покидает", "уходит", "уход", "прощани", "расторга", "расторж", "взаимном расторж",
    )
    rumour_terms = (
        "fichaje", "transfer", "signing", "подпис", "трансфер", "переход",
        "contactado", "contactos", "contact", "contacts", "контакт", "связался",
        "chelsea", "челси", "enreda", "enredo", "interes", "interés", "интерес",
    )
    if player and contains_any(text, departure_terms) and not contains_any(text, rumour_terms):
        return f"departure:{player}"

    if player and contains_any(
        text,
        rumour_terms
        + (
            "recompra", "recomprara", "buyback", "выкуп", "обратного выкупа", "venta", "sale", "продаж",
            "puja", "pide", "миллион",
        ),
    ):
        return f"transfer:rumour:{player}"

    if contains_any(text, ("femenino", "femenina", "женск", "фелисия шредер", "фелиция шредер")):
        return "women:real-madrid"

    tokens = [
        token
        for token in text.split()
        if len(token) > 2 and token not in STOPWORDS and not token.isdigit()
    ]
    return "generic:" + "-".join(tokens[:10])


def canonical_news_key(key: str) -> str:
    clean = (key or "").strip()
    if not clean:
        return ""
    text = normalize_news_text(clean.replace("generic:", " ").replace(":", " ").replace("-", " "))
    if is_venezuela_donation_text(text):
        return "club:donation:venezuela-earthquake"
    if is_joan_martinez_valencia_text(text):
        return "transfer:loan:joan-martinez-valencia"
    if is_laliga_rfef_meeting_text(text):
        return "club:laliga-rfef-meeting-skip"
    if is_olise_bayern_talks_text(text):
        return "transfer:olise-bayern-talks-real-monitoring"
    if is_asencio_loan_buy_text(text):
        return "transfer:loan:asencio-mandatory-buy"
    if is_nico_paz_como_text(text):
        return "transfer:nico-paz-como"
    if is_laporta_attacks_real_text(text):
        return "barca:laporta-attacks-real"
    return clean


def load_news_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return {canonical_news_key(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    except OSError:
        return set()


def save_news_keys(path: Path, keys: set[str]) -> None:
    path.write_text("\n".join(sorted(keys)) + ("\n" if keys else ""), encoding="utf-8")
