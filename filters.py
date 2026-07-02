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
        # National-team / World Cup noise that is not club-relevant enough for the channel.
        "world cup spotlight", "madrid world cup spotlight",
        "entra historia belgica", "historia belgica", "historia de belgica",
        "belgium history", "history of belgium",
        "france vs norway", "france against norway", "francia contra noruega", "francia noruega",
        "flipped the narrative", "during france vs norway",
        "agustin canobbio", "canobbio", "apellido verdugo real madrid", "expulsion contra espana",
        "channing tatum", "actor channing", "actor chenning", "norway and france", "noruega y francia",
        "uruguay vuelve firmar", "dolorosa eliminacion fase grupos", "dolorosa eliminacion", "fase de grupos",
        "bernardo silva stays on the bench", "portugal's 0-0 draw with colombia", "portugals 0-0 draw with colombia",
        "portugal 0-0 draw with colombia", "portugal colombia",
        "manolo lama", "lesion raphinha ha venido bien", "lesión raphinha ha venido bien",
        "no brasil ahora se siente superestrella", "todos van jugar el", "todos van a jugar el",
        "hora juegan madridistas mundial", "cuando juegan madridistas mundial", "madridistas mundial",
        "reranking europe top clubs player performance world cup", "top clubs player performance world cup",
        "reranking europe's top clubs", "player performance at the world cup", "player performance world cup",
        "rodrygo appears in miami", "rodrygo aparece en miami", "saca primera foto de equipo",
        "saca la primera foto de equipo", "primera foto equipo", "first team photo with bernardo",
        "first photo with summer signing", "shares first photo with summer signing",
        "image real madrid winger shares first photo", "real madrid winger shares first photo",
        "bienvenida rodrygo bernardo silva", "bienvenida rodrygo", "welcomes bernardo silva",
        "bienvenida de rodrygo", "la bienvenida de rodrygo", "bienvenida a bernardo silva",
        "rodrygo a bernardo silva",
        "dani carvajal 34 anos sobre futbol", "jovenes deben disfrutar deporte", "redes sociales ya quieren ser futbolistas",
        "young people should enjoy sport",

        # НЕ футбол (EN)
        "tennis", "nba", "nhl", "nfl", "mlb", "cricket", "cycling", "golf",
        "boxing", "ufc", "mma", "formula 1", "f1", "motogp",
        "horseracing", "horse racing", "darts", "snooker",
        "trent bridge", "new zealand", "stokes", "ben stokes", "third test", "test day",

        # НЕ футбол (RU)
        "теннис", "нба", "нхл", "нфл", "млб", "крикет", "велоспорт", "гольф",
        "бокс", "юфс", "мма", "мотогп", "шоссейные гонки",
        "конный спорт", "дартс", "снукер",
        "трент бридж", "стоукс", "новозеландск", "тестовый матч",

        # Баскетбол «Реала» и другие не-футбольные секции клуба.
        "basketball", "basket", "baloncesto", "liga endesa", "euroleague",
        "баскетбол", "евролига", "trey lyles", "трей лайлс", "scariolo", "скариоло",

        # Женская команда и академические/секционные новости пока не для основной ленты.
        "futbol femenino", "fútbol femenino", "real madrid femenino", "femenino", "femenina",
        "liga f", "grupo pau gasol", "pau gasol", "primera division femenina",
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
        "brazil scotland", "scotland", "шотланд", "knockout", "главное на чм-2026 за 5 минут",
        "главное на чм 2026 за 5 минут", "неймар и очоа", "бекхэм с бокалом",
        "шикарный винисиус", "юар", "world cup 2026", "сборную бразилии на чемпионате мира",
        "винисиус возглавляет сборную бразилии", "leading brazil in world cup",
        "vinicius is leading brazil", "vinicius junior brazil",
        "brasil en mundial", "con brasil en mundial", "за сборную бразилии на чемпионате мира",
        "сборной бразилии на чемпионате мира", "ronaldo nazario", "rivaldo", "romario",
        "роналду назарио", "ривалдо", "ромарио",
        "carlo ancelotti refuses engage japan mind games",
        "brazil manager carlo ancelotti refuses", "japan mind games",
        "round 32 clash world cup", "японских интеллектуальных играх",
        "анчелотти отказывается участвовать", "интеллектуальных играх",
        "как формируется новая бразилия", "new brazil taking shape",
        "new brazil is taking shape", "how new brazil is taking shape",
        "cunha plays key role", "кунь", "кунья играет ключевую роль",
        "bonito reencuentro cristiano ronaldo rodrygo",
        "cristiano ronaldo rodrygo portugues preocupo lesion",
        "cristiano ronaldo y rodrygo", "reencuentro cristiano rodrygo",
        "reencuentro cristiano-rodrygo", "cristiano-rodrygo",
        "прекрасная встреча криштиану роналду и родриго",
        "криштиану роналду и родриго", "возвращение криштиану и родриго",
        "португалец беспокоился о своей травме",
        "ronaldo nazario", "ronaldo nazário", "mbappe recuerda mi prime",
        "mbappe me recuerda", "мбаппе напоминает мне меня", "роналду назарио: мбаппе",
        "роналду забыл о винисиусе", "забыл о винисиусе",
        "я не вижу другого такого, как неймар", "другого такого, как неймар",
        "fede valverde's uruguay eliminated", "uruguay eliminated from 2026 world cup",
        "uruguay eliminated", "uruguay knocked out", "valverde's uruguay",
        "сборная уругвая", "уругвая из-за феде вальверде", "вылетела с чемпионата мира",
        "spain clinch first place", "marc cucurella features in win over uruguay",
        "features in win over uruguay", "win over uruguay", "first place in their group",
        "испания завоевала первое место", "голу марка кукуреллы", "победу над уругваем",
        "bellingham became tuchel", "bellingham has become tuchel",
        "tuchel's most important player", "tuchel most important player",
        "most important player for tuchel", "important player tuchel",
        "беллингем стал важнейшим игроком тухеля", "важнейшим игроком тухеля",
        "real madrid players still going strong at the world cup",
        "players still going strong at the world cup", "world cup for the round of 32",
        "round of 32", "по-прежнему сильны на чемпионате мира",
        "игроков мадридского \"реала\" по-прежнему сильны",
        "courtois belgica", "courtois belgium", "belgica siguen adelante",
        "goleada primeros grupo", "belgium continue", "first in the group",
        "куртуа и бельгия", "бельгия продолжа", "первое место в группе",
        "maldini sobre mundial vinicius", "maldini sobre el mundial", "mundial de vinicius",
        "ponerle en olimpo", "olimpo torneo", "mesa con mbappe", "mesa con messi",
        "турнирный олимп",
        "за одним столом с мбаппе или месси", "больше, чем криштиану",
        "luis suarez", "luís suarez", "луис суарес", "lionel messi", "лионель месси", "лионеля месси",
        "высказался об игре лионеля месси",
        "messi mbappe", "messi, mbappe", "vozinha", "opta",
        "символической сборной группового этапа", "сборной группового этапа чм",
        "norway vs france", "haaland on bench", "senegal iraq", "senegal - iraq",
        "норвегии, но мбаппе", "сенегал - ирак", "сенегал — ирак",
        "francia gana", "france wins", "hat-trick ousmane", "ousmane dembele",
        "asistencias kylian", "mbappe solidario", "mbappé solidario",
        "solidario mejor mundial", "mejor mundial", "mejor del mundial",
        "bielsa", "otra tactica", "otra táctica", "quieren otra tactica",
        "quieren otra táctica", "valverde y estrellas uruguay",
        "erling haaland sobre mas gusta espana", "erling haaland sobre más gusta españa",
        "me encanta venir aqui", "me encanta venir aquí", "estas vistas", "cuando marco gol",

        # Lifestyle вокруг легенд, даже если источник формально про Реал.
        "iphone", "айфон", "roberto carlos muestra iphone", "роберто карлос демонстрирует",
        "покрыт золотом", "стоит почти 18 000", "banado en oro", "bañado en oro",
        "antonio rudiger 33 anos futbolista real madrid infancia pobreza",
        "antonio rüdiger 33 anos futbolista real madrid infancia pobreza",
        "infancia pobreza", "infancia estuvo marcada", "pobreza",
        "si habia pollo en la mesa", "si había pollo en la mesa",
        "если на столе была курица", "детство было отмечено бедностью",

        # Подкасты и пересказы выпусков редко годятся для короткого новостного дайджеста.
        "podcast", "подкаст", "managing madrid podcast", "ведущий мадридского подкаста",

        # Личная драма вокруг соперников/бывших конфликтов без полезной клубной новости.
        "alex baena", "баэна", "fijacion conmigo", "fijación conmigo",
        "rencor", "обижаться", "простил", "привязан ко мне",
        "fallece padre ricardo carvalho", "padre de ricardo carvalho", "ricardo carvalho father",
        "father of ricardo carvalho", "скончался отец рикарду карвалью",

        # Ставки/букмекерка и около-Mbappe/MLS инфошум не подходят для канала.
        "best bets", "betting", "free 2026 world cup", "anytime goalscorer",
        "goalscorer picks", "odds", "букмекер", "букмекеров", "ставки", "ставках",
        "коэффициент", "коэффициенты", "mls move", "перехода в mls", "дэвидом бекхэмом",
        "david beckham", "beckham",

        # Низкосигнальные цитаты/радио-рубрики вокруг игроков соперников.
        "marc cucurella radio", "radio marca vinicius", "trabajo sucio", "dirty work",
        "грязную работу", "кукурелла на радио", "cucurella sobre interes", "кукурелла об интересе",
        "familia cule cucurella", "familia culé cucurella", "familia cule de cucurella",
        "familia culé de cucurella", "семья куле кукурельи",

        # Низкосигнальный блоговый кликбейт, опросы и generic-рубрики.
        "watching paint dry", "non-update", "non update", "spark", "transfer trap",
        "crystal-clear statement", "devastating news", "dream transfer target", "put on notice",
        "one game confirmed everything", "одна игра подтвердила все",
        "does carlo ancelotti hate endrick", "carlo ancelotti hate endrick", "hate endrick",
        "ненавидит эндрика", "так ли это на самом деле",
        "divertido momento marcelo linda caicedo", "divertido momento entre marcelo", "marcelo linda caicedo",
        "забавный момент между марсело и линдой кайседо",
        "it didn't take long for fede valverde", "center of controversy",
        "centre of controversy", "controversy again", "controversia", "polemica", "polémica",
        "micah richards told it like it is", "trent alexander-arnold controversy",
        "addressing trent alexander-arnold controversy",
        "toni kroos said what liverpool and bayern", "fans are terrified to confess",
        "gary neville affirmed", "real madrid fans have been saying for weeks",
        "fans have been saying for weeks about trent",
        "gary neville exfutbolista", "tuchel no ha querido en mundial",
        "alexander-arnold es clase mundial", "alexander arnold es clase mundial",
        "laterales propensos lesionarse",
        "giro mundial brahim", "lider con marruecos", "líder con marruecos",
        "marruecos real madrid mourinho", "leader with morocco",
        "rincon madrid en bellingham", "rincón madrid en bellingham", "bellingham tiene dos casas",
        "antiguo coto caza", "zonas verdes", "10 minutos santiago bernabeu",
        "уголок мадрида", "беллингема есть два дома", "охотничье угодье", "зеленые насаждения",
        "laporta contra cuerdas", "barcelona debe este ano", "barcelona debe este año",
        "goldman sachs", "camp nou", "лапорта", "голдман сакс",
        "champions league nightmare", "кошмар в лиге чемпионов",
        "xabi alonso's chelsea", "former real madrid defender", "бывшему защитнику мадридского \"реала\"",
        "juancho hernangomez", "juancho hernangómez", "хуанчо эрнангомес",
        "edu aguirre defiende cristiano", "menosprecia mundial michael olise",
        "лениво включать", "лень включать его в число 4 лучших игроков турнира",
        "google permite elegir medios favoritos", "medios favoritos", "любимые медиафайлы",
        "smiles & casualties", "smiles casualties", "moving on", "general/",
        "lectores defensa central", "lectores", "aprueban forma masiva", "rechazan vender",
        "encuesta", "87%", "60%", "se opone", "palo de arda", "palo arda", "un palo",
        "anti-endrick", "anti endrick", "anti-endrik", "anti endrik",
        "4 champions eclipsan", "eclipsan eliminatoria seleccion", "ni 4 campeones", "ни 4 чемпиона",
        "so much for the endrick breakout", "endrick breakout under carlo ancelotti",
        "прорыв эндрика под руководством карло анчелотти",
        "real madrid c mantener plaza segunda rfef", "real madrid c mantener", "segunda rfef",
        "втором дивизионе рфпл", "втором дивизионе rfef", "реал c может",
        "george weah", "weah said what", "fans have been whispering",
        "lamine yamal", "джордж веа", "ямаля",
        "chelsea sign italian defender", "chelsea signs italian defender", "palestra",
        "juanma rodriguez filtros mbappe francia", "juanma rodriguez without filters",
        "sin filtros sobre mbappe en francia",
        "mbappe in france", "мбаппе в сборной франции", "комментарии родригеса",
        "toni kroos got brutally honest", "florian wirtz and jamal musiala",
        "wirtz and musiala", "jamal musiala stack up with jude bellingham",
        "флориан виртц и джамал музиала", "виртц и джамал мусиала",
        "david alaba claro jugar espana", "jugar espana especial mi",
        "jugar en espana es especial", "jugar en españa es especial",
        "alaba claro: jugar",
        "alaba claro jugar espana", "играть в испании особенно",
        "yamal cucurella", "lamine yamal cucurella",
        "я его съем", "противостоянии с кукурельей",
        "barca copia real madrid desesperada firmar julian alvarez",
        "barca copia al real madrid desesperada firmar",
        "barca copia al real madrid desesperada por firmar",
        "barcelona copies real madrid",
        "desesperada firmar julian alvarez",
        "desesperada por firmar julian alvarez",
        "хулиана маньяра альвареса",
        "rincon donde desconecta luka modric", "rincón donde desconecta luka modric",
        "comer carne a la brasa", "7 minutos del estadio santiago bernabeu",

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
