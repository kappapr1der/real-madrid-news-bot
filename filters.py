import re
import logging
import unicodedata
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

# --- Нормализация текста ------------------------------------------------------
def _normalize(text: str) -> str:
    """
    Приводим текст к низкому регистру + NFKC, убираем «фигурные» кавычки/дефисы.
    Это повышает устойчивость к странной пунктуации и кодировкам.
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text).lower().strip()
    # Унификация дефисов/тире/двоеточий/многоточий
    replacements = {
        "—": "-", "–": "-", "-": "-",
        "“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "’": "'", "‚": "'",
        "…": "...", "：": ":", "·": " ",
    }
    for k, v in replacements.items():
        t = t.replace(k, v)
    # Сжать многопробелы
    t = re.sub(r"\s+", " ", t)
    return t

# --- Списки фильтров ----------------------------------------------------------
FILTERS = {
    "whitelist": [
        # Реал Мадрид и синонимы
        "real madrid", "rmcf", "реал мадрид", "реал", "мадридисты",
        "bernabeu", "бернабеу", "сантьяго бернабеу",
        "los blancos", "blancos", "сливочные", "галактикос",

        # Персоны Реала (добавлены тренеры/чиновники)
        "vinicius", "винисиус", "rodrygo", "родриго", "bellingham", "беллингем",
        "kroos", "кроос", "modric", "модрич", "camavinga", "камавинга",
        "tchouameni", "тчуамени", "чуамени", "valverde", "вальверде",
        "courtois", "куртуа", "lunin", "лунин", "militao", "милитао",
        "rudiger", "рюдигер", "carvajal", "карвахаль", "mendy", "менди",
        "brahim", "диас", "arda guler", "ардаи", "арда гюлер",
        "ancelotti", "анчеротти", "анчелотти", "florentino perez", "перес",

        # Маркеры клубного контекста
        "castilla", "кастилья",
    ],
    "greylist": [
        # Турниры и соперники по контексту (требуют связки с Реалом)
        "champions league", "uefa champions league", "ucl",
        "la liga", "laliga", "primera", "примера", "ла лига",
        "copa del rey", "кубок испании", "supercopa", "суперкубок испании",
        "uefa", "fifa",

        # Частые оппоненты/гранды
        "barcelona", "барселона", "барса", "fcb",
        "atletico", "атлетико", "atm", "atl",
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
    
        "рпл",
        "российская премьер-лига",
        "rpl",
        "спартак",
        "цска",
        "зенит",
        "локомотив",
        "рубин",
        "динамо москва",
        "динамо-москва",
        "пари нн",
        "нижний новгород",
        "пари нижний новгород",
        "ахмат",
        "крылья советов",
        "ростов",
        "урал",
        "факел",
        "кахабер тбилиси",
        "химки",
        "балтика",
        "одинцово",
        "торпедо москва",
        "торпедо-москва",],
}

# Быстрые lookup-наборы
_WHITELIST = tuple(FILTERS["whitelist"])
_GREYLIST = tuple(FILTERS["greylist"])
_BLACKLIST = tuple(FILTERS["blacklist"])

# --- Паттерны матчапов --------------------------------------------------------
MATCHUP_PATTERNS = [
    # Эль Класико
    re.compile(r"(rm|rma|real madrid|реал)[\s\-:]*v[s]?[.\s\-:]*?(fcb|barcelona|барса|барселона)", re.IGNORECASE),
    # Мадридское дерби
    re.compile(r"(rm|rma|real madrid|реал)[\s\-:]*v[s]?[.\s\-:]*?(atm|atl|атлетико|атлети)", re.IGNORECASE),
]

# Сильные оппоненты для еврокубков
UCL_OPPONENTS = [
    "bayern", "psg", "juventus", "milan", "inter", "napoli",
    "manchester city", "chelsea", "arsenal", "liverpool",
    "dortmund", "leipzig", "porto", "benfica", "sporting",
    "celtic", "rangers", "atalanta", "monaco", "marseille",
    "ajax", "feyenoord", "psv", "roma", "lazio",
]

# Антиспам: храним последние 300 заголовков (нормализованных)
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
    :param source: опционально — домен/бренд источника (для будущих правил)
    """
    if not text:
        logger.info("[FILTERED: EMPTY]")
        return False

    # Дубль по заголовку
    if is_duplicate(text):
        return False

    # Нормализованные тексты
    title = _normalize(text)
    body = _normalize(summary) if summary else ""

    # 1) Жёсткий бан по blacklist (в т.ч. «Кубок Стэнли» и пр.)
    if _matches_any(title, _BLACKLIST) or (body and _matches_any(body, _BLACKLIST)):
        logger.info(f"[FILTERED: BLACKLIST] {text[:90]}...")
        return False

    # 2) Специальные кейсы: Эль Класико и дерби
    if re.search(r"(el[\s\-]?clas[íi]co|эль\s?класико|эль\s?класико|эль\s?класико)", title):
        if "real madrid" in title or "реал" in title:
            logger.info(f"[PASSED: CLASICO+REAL] {text[:90]}...")
            return True
        logger.info(f"[FILTERED: CLASICO w/o REAL] {text[:90]}...")
        return False

    # 3) Шаблоны матчапов с Реалом
    for pattern in MATCHUP_PATTERNS:
        if pattern.search(title):
            logger.info(f"[PASSED: MATCHUP] {text[:90]}...")
            return True

    # 4) Мачапы UCL уровня: "Real Madrid vs (Bayern|PSG|...)" — на всякий случай широким паттерном
    ucl_pattern = re.compile(
        rf"(rm|rma|real madrid|реал)[\s\-:]*v[s]?[.\s\-:]*(?:{'|'.join(UCL_OPPONENTS)})",
        re.IGNORECASE
    )
    if ucl_pattern.search(title):
        logger.info(f"[PASSED: REAL IN UCL] {text[:90]}...")
        return True

    # 5) Белый список ключевых маркеров Реала
    if _matches_any(title, _WHITELIST) or (body and _matches_any(body, _WHITELIST)):
        logger.info(f"[PASSED: WHITELIST] {text[:90]}...")
        return True

    # 6) Серый список (только если есть прямое упоминание Реала в заголовке/теле)
    if _matches_any(title, _GREYLIST) or (body and _matches_any(body, _GREYLIST)):
        if "real madrid" in title or "реал" in title or ("real madrid" in body or "реал" in body):
            logger.info(f"[PASSED: GREYLIST+REAL] {text[:90]}...")
            return True
        logger.info(f"[FILTERED: GREYLIST w/o REAL] {text[:90]}...")
        return False

    # 7) Не нашли прямых маркеров — отсекаем
    logger.info(f"[FILTERED: NO MATCH] {text[:90]}...")
    return False

def filter_news(text: str, summary: Optional[str] = None, source: Optional[str] = None) -> bool:
    """
    Обёртка для совместимости. Старые вызовы с одним аргументом продолжают работать.
    """
    return passes_filters(text, summary=summary, source=source)
