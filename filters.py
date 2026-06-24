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
        "bernabeu", "bernábeu", "бернабеу", "сантьяго бернабеу",
        "los blancos", "blancos", "сливочные", "галактикос",
        "la fabrica", "la fábrica", "фабрика", "кастилья", "castilla",

        # Игроки, тренеры и клубные фигуры
        "vinicius", "vinícius", "винисиус", "виниций", "rodrygo", "родриго",
        "mbappe", "mbappé", "мбаппе", "bellingham", "беллингем",
        "endrick", "эндрик", "gonzalo garcia", "gonzalo garcía", "gonzalo", "гонсало гарсия", "гонсало",
        "nico paz", "нико пас", "mastantuono", "мастантуоно",
        "arda guler", "arda güler", "арда", "арда гюлер",
        "valverde", "вальверде", "tchouameni", "tchouaméni", "тчуамени", "чуамени",
        "camavinga", "камавинга", "modric", "modrić", "модрич", "kroos", "кроос",
        "ceballos", "себальос", "brahim", "брахим", "диас",
        "courtois", "куртуа", "lunin", "лунин", "militao", "militão", "милитао",
        "rudiger", "rüdiger", "рюдигер", "carvajal", "карвахаль",
        "trent", "alexander-arnold", "александер-арнольд", "трент",
        "huijsen", "хейсен", "хуисен", "asencio", "асенсио",
        "alaba", "алаба", "mendy", "менди", "fran garcia", "fran garcía", "фран гарсия",
        "carreras", "каррерас", "olise", "олисе", "konate", "konaté", "конате",
        "enzo fernandez", "enzo fernández", "энцо фернандес", "cucurella", "кукурелья",
        "ancelotti", "анчеротти", "анчелотти", "mourinho", "мourinho", "моруинью", "моуринью",
        "xabi alonso", "хаби алонсо", "arbeloa", "арбеоа",
        "florentino perez", "florentino pérez", "florentino", "флорентино", "перес",
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

        # Баскетбол «Реала» и другие не-футбольные секции клуба.
        "basketball", "basket", "baloncesto", "liga endesa", "euroleague",
        "баскетбол", "евролига", "trey lyles", "трей лайлс", "scariolo", "скариоло",

        # Женская команда и академические/секционные новости пока не для основной ленты.
        "futbol femenino", "fútbol femenino", "real madrid femenino", "femenino", "femenina",
        "felicia schroder", "felicia schröder", "фелисия шредер", "фелиция шредер",
        "женский реал", "женская команда", "женского реала",

        # Хоккей и «Кубок Стэнли»
        "stanley cup", "кубок стэнли", "хоккей", "кхл", "шайба",

        # Музыка/кино/шоу/политика/прочее
        "fashion", "music", "movie", "concert", "celebrity",
        "политика", "выборы", "elections", "war", "война",
        "economy", "business", "экономика", "бизнес",

        # Нерелевантные рубрики на профильных сайтах
        "quiz", "who am i", "sensational", "cromos", "sticker", "stickers",
        "путевк", "карточк", "налог", "tributar", "irpf",
        "playas para perros", "perros", "dogs", "собак",

        # Lifestyle/туризм вокруг бывших фигур клуба: это не новость о Реале.
        "refugio", "pueblo", "habitantes", "senderismo", "paraje natural", "siglo xii",
        "paseo", "paseo maritimo", "marítimo", "murallas", "fortaleza frente mar",
        "ocio", "playa", "nабережная", "набережная", "прогулок пешком",

        # Общий ЧМ/сборные без прямой ценности для ленты «Реала».
        "golden boot", "bota de oro", "золотой бутс", "undav", "dumfries", "aruba",
        "tunisia", "тунис", "renard", "ренар", "белой рубашке",
        "ni lamine yamal ni mbappe", "oyarzabal", "оярсабаль", "record historico jugador espana",
        "espana arabia", "saudi arabia", "arabia saudi", "celebracion mas especial",
        "maldini sobre aspiraciones", "aspiraciones espana", "aspiraciones españa",
        "maldini sobre las aspiraciones", "aspiraciones de espana", "aspiraciones de españa",
        "gran favorita", "ultimo partido no primero", "último partido no primero",
        "dembele", "dembélé", "дембеле", "в адрес дембеле",
        "pinguino", "pingüino", "mujer", "sus hijos", "wife", "children",
        "pareja de marc cucurella", "pareja marc cucurella", "desvela gesto",
        "marc cucurella desvela", "партнер марка кукуреллы",

        # Общие live/open-thread/recap посты по ЧМ и сборным без клубного угла.
        "world cup open thread", "open thread", "открытая трансляция чемпионата мира",
        "открытая трансляция чемпионата мира по футболу", "чемпионата мира по футболу |",
        "resumen mundial", "world cup recap", "итоги чемпионата мира",
        "england held by ghana", "held by ghana", "ghana", "гана", "jordan ayew", "айю",
        "france iraq", "франция", "ирак", "storms cause havoc", "storm", "шторм",

        # Ставки/букмекерка и около-Mbappe/MLS инфошум не подходят для канала.
        "best bets", "betting", "free 2026 world cup", "anytime goalscorer",
        "goalscorer picks", "odds", "букмекер", "букмекеров", "ставки", "ставках",
        "коэффициент", "коэффициенты", "mls move", "перехода в mls", "дэвидом бекхэмом",
        "david beckham", "beckham",

        # Низкосигнальные цитаты/радио-рубрики вокруг игроков соперников.
        "marc cucurella radio", "radio marca vinicius", "trabajo sucio", "dirty work",
        "грязную работу", "кукурелла на радио",

        # Низкосигнальный блоговый кликбейт, опросы и generic-рубрики.
        "watching paint dry", "non-update", "non update", "spark", "transfer trap",
        "crystal-clear statement", "devastating news", "dream transfer target", "put on notice",
        "smiles & casualties", "smiles casualties", "moving on", "general/",
        "lectores defensa central", "lectores", "aprueban forma masiva", "rechazan vender",
        "encuesta", "87%", "60%", "se opone", "palo de arda", "palo arda", "un palo",
        "anti-endrick", "anti endrick", "anti-endrik", "anti endrik",

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

REAL_SOURCE_TOPIC_MARKERS = [
    "fichaje", "fichajes", "transfer", "mercado", "market",
    "salida", "sale", "venta", "sell", "sold", "loan", "cesion", "cesión",
    "renueva", "renovacion", "renovación", "renewal", "contract", "contrato",
    "lesion", "lesión", "injury", "diagnosis", "recupera", "return",
    "cantera", "canterano", "academy", "squad", "plantilla", "lineup",
    "partido", "match", "liga", "champions", "bernabeu", "bernábeu",
    "gol", "goal", "defensa", "midfield", "centro del campo",
]

_WHITELIST = tuple(FILTERS["whitelist"])
_GREYLIST = tuple(FILTERS["greylist"])
_BLACKLIST = tuple(FILTERS["blacklist"])
_REAL_SOURCE_MARKERS = tuple(REAL_SOURCE_MARKERS)
_REAL_SOURCE_TOPIC_MARKERS = tuple(REAL_SOURCE_TOPIC_MARKERS)

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


def _real_source_has_topic_signal(title: str, body: str) -> bool:
    return (
        _matches_any(title, _WHITELIST)
        or (body and _matches_any(body, _WHITELIST))
        or _matches_any(title, _REAL_SOURCE_TOPIC_MARKERS)
        or (body and _matches_any(body, _REAL_SOURCE_TOPIC_MARKERS))
    )


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
        if _real_source_has_topic_signal(title, body):
            logger.info(f"[PASSED: REAL SOURCE] {source}: {text[:90]}...")
            return True
        logger.info(f"[FILTERED: REAL SOURCE LOW SIGNAL] {source}: {text[:90]}...")
        return False

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
