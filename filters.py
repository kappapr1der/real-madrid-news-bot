import re
import logging
import unicodedata
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """
    Приводим текст к низкому регистру + NFKC, убираем «фигурные» кавычки/дефисы.
    Это повышает устойчивость к странной пунктуации и кодировкам.
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text).lower().strip()
    replacements = {
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "„": '"',
        "«": '"',
        "»": '"',
        "’": "'",
        "‚": "'",
        "…": "...",
        "：": ":",
        "·": " ",
    }
    for k, v in replacements.items():
        t = t.replace(k, v)
    t = re.sub(r"\s+", " ", t)
    return t


FILTERS = {
    "whitelist": [
        # Реал Мадрид и синонимы
        "real madrid", "rmcf", "реал мадрид", "реал", "мадридисты",
        "bernabeu", "бернабеу", "сантьяго бернабеу",
        "los blancos", "blancos", "сливочные", "галактикос",
        "la fabrica", "la fábrica", "фабрика", "кастилья", "castilla",

        # Игроки, тренеры и клубные фигуры
        "vinicius", "vinícius", "винисиус", "rodrygo", "родриго",
        "mbappe", "mbappé", "мбаппе", "bellingham", "беллингем",
        "endrick", "эндрик", "gonzalo garcia", "gonzalo garcía", "гонсало гарсия",
        "mastantuono", "мастантуоно", "arda guler", "arda güler", "арда", "арда гюлер",
        "valverde", "вальверде", "tchouameni", "tchouaméni", "тчуамени", "чуамени",
        "camavinga", "камавинга", "modric", "modrić", "модрич", "kroos", "кроос",
        "ceballos", "себальос", "brahim", "брахим", "диас",
        "courtois", "куртуа", "lunin", "лунин", "militao", "militão", "милитао",
        "rudiger", "rüdiger", "рюдигер", "carvajal", "карвахаль",
        "trent", "alexander-arnold", "александер-арнольд", "трент",
        "huijsen", "хейсен", "хуисен", "asencio", "асенсио",
        "alaba", "алаба", "mendy", "менди", "fran garcia", "fran garcía", "фран гарсия",
        "carreras", "каррерас", "ancelotti", "анчеротти", "анчелотти",
        "xabi alonso", "хаби алонсо", "arbeloa", "арбеоа", "florentino perez", "florentino pérez", "перес",
    ],
    "greylist": [
        # Турниры и соперники по контексту (требуют связки с Реалом)
        "champions league", "uefa champions league", "ucl",
        "la liga", "laliga", "primera", "примера", "ла лига",
        "copa del rey", "кубок испании", "supercopa", "суперкубок испании",
        "club world cup", "mundial de clubes", "клубный чемпионат мира",
        "uefa", "fifa",

        # Частые оппоненты/гранды
        "barcelona", "барселона", "барса", "fcb",
        "atletico", "atlético", "атлетико", "atm", "atl",
        "manchester city", "манчестер сити", "city",
        "chelsea", "arsenal", "liverpool", "bayern", "psg",
        "juventus", "milan", "inter", "napoli", "dortmund",
        "leipzig", "porto", "benfica", "sporting", "sevilla",
        "real sociedad", "villarreal", "girona",
    ],
    "blacklist": [
        # НЕ футбол (EN)
        "tennis", "nba", "nhl", "nfl", "mlb", "cricket", "cycling", "golf",
        "boxing", "ufc", "mma", "formula 1", "f1", "motogp",
        "horseracing", "horse racing", "darts", "snooker",

        # НЕ футбол (RU)
        "теннис", "нба", "нхл", "нфл", "млб", "крикет", "велоспорт", "гольф",
        "бокс", "юфс", "мма", "мотогп", "шоссейные гонки",
        "конный спорт", "дартс", "снукер",

        # Хоккей и «Кубок Стэнли»
        "stanley cup", "кубок стэнли", "хоккей", "кхл", "шайба",

        # Музыка/кино/шоу/политика/прочее
        "fashion", "music", "movie", "concert", "celebrity",
        "политика", "выборы", "elections", "war", "война",
        "economy", "business", "экономика", "бизнес",

        # Российский футбол, если новость не имеет явной связи с Реалом
        "рпл", "российская премьер-лига", "rpl",
        "спартак", "цска", "зенит", "локомотив", "рубин",
        "динамо москва", "динамо-москва", "пари нн", "нижний новгород",
        "пари нижний новгород", "ахмат", "крылья советов", "ростов",
        "урал", "факел", "кахабер тбилиси", "химки", "балтика",
        "одинцово", "торпедо москва", "торпедо-москва",
    ],
}

REAL_SOURCE_MARKERS = [
    "real madrid",
    "реал мадрид",
    "managing madrid",
    "madrid universal",
    "the real champs",
    "real madrid news",
    "football españa - real madrid",
    "football espana - real madrid",
    "marca - real madrid",
    "defensa central",
    "bernabeu digital",
    "bernabéu digital",
    "mundo deportivo - real madrid",
    "sport - real madrid",
]

_WHITELIST = tuple(FILTERS["whitelist"])
_GREYLIST = tuple(FILTERS["greylist"])
_BLACKLIST = tuple(FILTERS["blacklist"])
_REAL_SOURCE_MARKERS = tuple(REAL_SOURCE_MARKERS)

MATCHUP_PATTERNS = [
    re.compile(r"(rm|rma|real madrid|реал)[\s\-:]*v[s]?[.\s\-:]*?(fcb|barcelona|барса|барселона)", re.IGNORECASE),
    re.compile(r"(rm|rma|real madrid|реал)[\s\-:]*v[s]?[.\s\-:]*?(atm|atl|atlético|атлетико|атлети)", re.IGNORECASE),
]

UCL_OPPONENTS = [
    "bayern", "psg", "juventus", "milan", "inter", "napoli",
    "manchester city", "chelsea", "arsenal", "liverpool",
    "dortmund", "leipzig", "porto", "benfica", "sporting",
    "celtic", "rangers", "atalanta", "monaco", "marseille",
    "ajax", "feyenoord", "psv", "roma", "lazio",
]

recent_texts = deque(maxlen=300)


def is_duplicate(text: str) -> bool:
    norm = _normalize(text)
    if not norm:
        return False
    if norm in recent_texts:
        logger.info(f"[FILTERED: DUPLICATE] {text[:90]}...")
        return True
    recent_texts.append(norm)
    return False


def _matches_any(haystack: str, needles: tuple) -> bool:
    return any(n in haystack for n in needles)


def passes_filters(text: str, summary: Optional[str] = None, source: Optional[str] = None) -> bool:
    """
    Основной фильтр релевантности.
    :param text: заголовок/лид
    :param summary: опционально — подводка/анонс
    :param source: опционально — бренд источника. Профильные источники Real Madrid проходят мягче.
    """
    if not text:
        logger.info("[FILTERED: EMPTY]")
        return False

    if is_duplicate(text):
        return False

    title = _normalize(text)
    body = _normalize(summary) if summary else ""
    source_name = _normalize(source) if source else ""

    if _matches_any(title, _BLACKLIST) or (body and _matches_any(body, _BLACKLIST)):
        logger.info(f"[FILTERED: BLACKLIST] {text[:90]}...")
        return False

    if source_name and _matches_any(source_name, _REAL_SOURCE_MARKERS):
        logger.info(f"[PASSED: REAL SOURCE] {source}: {text[:90]}...")
        return True

    if re.search(r"(el[\s\-]?clas[íi]co|эль\s?класико)", title):
        if "real madrid" in title or "реал" in title:
            logger.info(f"[PASSED: CLASICO+REAL] {text[:90]}...")
            return True
        logger.info(f"[FILTERED: CLASICO w/o REAL] {text[:90]}...")
        return False

    for pattern in MATCHUP_PATTERNS:
        if pattern.search(title):
            logger.info(f"[PASSED: MATCHUP] {text[:90]}...")
            return True

    ucl_pattern = re.compile(
        rf"(rm|rma|real madrid|реал)[\s\-:]*v[s]?[.\s\-:]*(?:{'|'.join(UCL_OPPONENTS)})",
        re.IGNORECASE,
    )
    if ucl_pattern.search(title):
        logger.info(f"[PASSED: REAL IN UCL] {text[:90]}...")
        return True

    if _matches_any(title, _WHITELIST) or (body and _matches_any(body, _WHITELIST)):
        logger.info(f"[PASSED: WHITELIST] {text[:90]}...")
        return True

    if _matches_any(title, _GREYLIST) or (body and _matches_any(body, _GREYLIST)):
        if "real madrid" in title or "реал" in title or ("real madrid" in body or "реал" in body):
            logger.info(f"[PASSED: GREYLIST+REAL] {text[:90]}...")
            return True
        logger.info(f"[FILTERED: GREYLIST w/o REAL] {text[:90]}...")
        return False

    logger.info(f"[FILTERED: NO MATCH] {text[:90]}...")
    return False


def filter_news(text: str, summary: Optional[str] = None, source: Optional[str] = None) -> bool:
    """
    Обёртка для совместимости. Старые вызовы с одним аргументом продолжают работать.
    """
    return passes_filters(text, summary=summary, source=source)
