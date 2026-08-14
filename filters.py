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
        "enzo fernandez", "enzo fernández", "энцо фернандес",
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
        # Freshly observed feed leakage: neither rival-only news nor former-player
        # national-team features belong in the Real Madrid editorial stream.
        "chelsea poised to sign morgan rogers", "morgan rogers from aston villa",
        "cucurella quiere asaltar el olimpo", "кукурелья хочет штурмовать олимп",
        "zidane ya tiene fecha para ser seleccionador", "зидан уже назначен на пост главного тренера сборной франции",
        "jude bellingham is england's next captain", "следующий капитан сборной англии",
        "partido de sus vidas", "prensa pide segunda estrella", "вся пресса требует вторую звезду",
        "alba redondo cerca de fichar por la juventus", "альба редондо близка к переходу в ювентус",

        # July 20 morning: pundit takes, unrelated World Cup coverage, and anonymous
        # transfer clickbait are not stories for the club feed.
        "tomas guasch", "tomás guasch", "томас гуаш", "fichar olise es capricho",
        "spain and marc cucurella crowned world cup champions", "cucurella crowned world cup champions",
        "rodri rodri rodri", "rodri, rodri, rodri", "toni kroos heroico triunfo espana", "toni kroos y el heroico triunfo",
        "heroic spain triumph kroos",
        "real madrid fichado lateral izquierdo mundo", "real madrid has signed the best left back in the world",
        "real madrid defender determined to stay", "potentially blocking alessandro bastoni move",
        "mantienen el bloqueo al fichaje de yan diomande por el psg", "bloqueo al fichaje de yan diomande por el psg",
        "once ideal del mundial", "ideal world cup xi",
        "real madrid have doubts over the suitability of superstar trio", "doubts over the suitability of superstar trio",
        "letras gigantes acero inoxidable fachada bernabeu", "aparece incognita sobre letras gigantes acero inoxidable",
        "iris ashley deja real madrid", "iris ashley deja el real madrid",
        "real madrid consider move for bayern munich superstar unfeasible",
        "quillo barrios comunicador", "argentina tiene grandeza madrid",
        "courtois presentara plataforma inversion madrid",
        "mendy entrena cesped lunin gimnasio", "mendy entrena cesped, lunin gimnasio",
        "novedades mercado afirman interes ferran torres", "novedades mercado: afirman interes ferran torres",
        "vinicius luce nueva imagen",
        "carlo ancelotti was right about wanting this spanish midfielder at real madrid in 2022",
        "verstappen", "red bull", "ферстаппен", "ред булл",

        # July 21 evening: membership marketing, World Cup age trivia, and
        # video-game promotion do not belong in the club-news digest.
        "new season campaign", "become an official real madrid fan",
        "campana nueva temporada", "hazte aficionado oficial real madrid",
        "empieza la nueva temporada como fan oficial",
        "how old will every real madrid player be at the 2030 world cup",
        "edad tendran todos jugadores real madrid proximo mundial 2030",
        "la edad que tendrán todos los jugadores del real madrid en el próximo mundial 2030",
        "fc27", "portada fc27",

        # July 22: national-team side stories, lifestyle pieces, women's-team
        # transfers, and generic clickbait must not displace club news.
        "enzo fernandez says argentina played with pride and humility",
        "morgan rogers",
        "sensible changes",
        "vinicius 26 sobre su familia", "vivi con mi abuela nilza", "grandmother nilza",
        "problema real madrid sigue sin resolver", "the problem real madrid have still not solved",
        "ea fc 27", "ea fc27",
        "real madrid misses out on the chance to sign one of europes best defenders",
        "real madrid miss out on the chance to sign one of europe's best defenders",
        "alba redondo deja real madrid", "alba redondo leaves real madrid",
        "doris dipetta", "madre de fede valverde",

        # July 22 evening: World Cup XI roundups, generic valuation chatter,
        # and home-appliance clickbait are outside the club-news beat.
        "three real madrid players included in the 2026 fifa world cup best xi",
        "mundial dispara real madrid", "mundial dispara al real madrid",
        "expertos en climatizacion", "expertos en climatización",
        "air conditioning remote",
        "real madrid trio see market values soar after impressive world cup displays",
        "every real madrid fan has been asking for",

        # July 23: keep general-football roundups, celebrity reactions and
        # former-player updates out of the Real Madrid editorial lane.
        "afa statement on president's detention", "afa statement on the president's detention",
        "torres ready to leave barcelona",
        "заявление afa о задержании президента", "торрес готов покинуть барселону",
        "raul arevalo", "raul arévalo",
        "real madrid land 3 stars in fifa's official best xi",
        "modric renueva con milan", "modric renueva con el milan", "modric renews with milan",
        "calendario pretemporada 2026/27: fechas, horarios y donde ver todos los amistosos",
        "calendario de pretemporada 2026/27: fechas, horarios y donde ver todos los amistosos",
        "desvelan intrahistoria fichaje pedrerol chiringuito mediaset",
        "intrahistoria del fichaje de pedrerol",

        # July 24: lifestyle, ticketing, basketball and stale/former-player
        # material do not belong in the football news digest.
        "one of the bright spots of real madrid's season ready to take another leap",
        "psg dispuesto a romper definitivamente el fichaje de enzo por el real madrid",
        "would not accept transfer: insider floats possibility of karim benzema",
        "glavnyj trener rodiny oharakterizoval novichka",
        "главный тренер родины охарактеризовал новичка",
        "expertos en cirugia plastica coinciden", "expertos en cirugía plástica coinciden",
        "compra tus entradas betis vs real madrid",
        "sergio llull", "серхио люлль",
        "maria trisac", "мария трисак",
        "vinicius da la cara y presume de nueva imagen", "винисиус поворачивается лицом и хвастается",
        "zidane set to be announced as mbappe and tchouameni",
        "reflexion iker casillas 45 anos", "reflexión iker casillas 45 años",

        # July 25-26: personal lifestyle, unrelated fixtures and generic daily
        # columns must not take places from actual club news.
        "courtois ensena espectacular porsche gt3", "courtois muestra su porsche gt3",
        "courtois o de bruyne", "courtois o de bruyne quien vale mas",
        "кто из бывших друзей и легенд сборной бельгии стоит дороже",
        "real sociedad con zakharyan se impone al wolves", "реал сосьедад с захаряном одержал победу над вулверхэмптоном",
        "i prefer not to speak", "я предпочитаю молчать 26 июля 2026",

        # July 27: generic award chatter, historical club trivia and a leaked
        # cricket item are not actionable Real Madrid news.
        "balon de oro marca las normas", "balón de oro marca las normas",
        "mbappe se coloca como principal candidato", "mbappé se coloca como principal candidato",
        "the last time in budapest", "реал возвращается в будапешт",
        "craig overton", "battle with brother jamie", "dramatic hundred finish",

        # July 27 evening: rival-only transfer news and personal World Cup
        # reflections do not carry a concrete club update.
        "welbeck", "уэлбек",
        "carta abierta mbappe", "carta abierta mbappé", "carta abierta de mbappe", "carta abierta de mbappé",
        "open letter mbappe", "открытое письмо мбаппе",
        "endrick 20 anos cuando era nino", "endrick 20 años cuando era niño",
        "mi madre solia llevarse biblia", "mi madre solía llevarse biblia",
        "no teniamos tv ni internet en casa", "no teníamos tv ni internet en casa",
        "у нас дома не было телевизора или интернета",

        # July 28: vague transfer-window clickbait, non-club national-team updates,
        # and pundit-only speculation add noise without a concrete club event.
        "real madrid are finally realising their biggest mistake", "finally realising their biggest mistake of this transfer window",
        "kylian mbappe 27 anos no voy a ser entrenador", "kylian mbappé 27 años no voy a ser entrenador",
        "no voy a ser entrenador despues de mi carrera", "no voy a ser entrenador después de mi carrera",
        "zinedine zidane confirmed as france manager", "zidane confirmed as new france manager",
        "chelsea unveil trialist in first game under xabi alonso", "first game under xabi alonso",
        "aritz gabilondo", "aritz gabilondo comunicador sobre llegada mastantuono real sociedad",
        "real madrid baraja nombres heredero thibaut courtois", "heredero thibaut courtois",
        "madrid se mete en un problema", "real madrid faces the need for operations in the transfer market",

        # July 29: source-label clickbait and vague warnings do not carry a
        # concrete, independently checkable club update.
        "aviso jose felix diaz pone alerta madridismo", "aviso de jose felix diaz pone en alerta al madridismo",
        "real madrid's move for rodri may have just hit a major stumbling block",
        "fabrizio romano offers the michael olise clarity real madrid fans needed",
        "fabrizio romano drops bombs", "fabrizio romano suelta bombas",

        # July 29 evening: federation process notes, historical rankings, and
        # salary hypotheticals are not current club updates.
        "uefa sobre planes fifa", "uefa on fifa plans", "fifa deadline for federations",
        "ranking where real madrid teams stand among the best champions league winners since 2020",
        "tomas roncero si vinicius acepta cobrar", "si vinicius acepta cobrar", "vinicius accepts earning",
        "si vinicius acepta cobrar entre 5 7 millones menos mbappe",

        # July 30 morning: commentary, former-player moves without a club impact,
        # and unsupported analyst claims must not pad an otherwise short digest.
        "ancelotti italy", "carlo ancelotti italy brazil coach", "turned down italy job",
        "kylian mbappe and the ewing theory",
        "fracaso deportivo", "fracaso deportivo record gastos real madrid",
        "florentino se ha puesto las pilas", "silencio vinicius no es justo", "silencio de vinicius no es justo",
        "bayer target former real madrid", "bayer target former real madrid left back miguel gutierrez",
        "hector gonzalez", "hector gonzalez analista deportivo",

        # July 30 daytime: fan columns and automated daily threads are not
        # standalone news, even when they mention current squad players.
        "davoo xeneize", "davoo xeneize comunicador",
        "david trezeguet said what even real madrid fans failed to realize",
        "daily thread", "hilo diario",

        # July 30 evening: generic rival-transfer coverage, anonymous rumours,
        # personal commentary and historical features do not earn a digest slot.
        "carlo ancelotti officially made the casemiro realization",
        "delantero tapado pedia mourinho", "delantero tapado que pedia mourinho",
        "maxence lacroix", "jaime marcos psicologo",
        "caso video sexual", "jueza caso video sexual canteranos", "jueza del caso video sexual canteranos",
        "caso video sexual canteranos real madrid",
        "fotografia inedita ricardo zamora", "fotografia inédita ricardo zamora",

        # July 31: media-company chatter, unfounded ultimatums and lifestyle
        # stories do not belong in the club news digest.
        "josep pedrerol", "rodri just joined rare company",
        "vinicius ultimatum", "real madrid vinicius ultimatum",
        "vinicius saca su lado paterno", "vinicius saca lado paterno",
        "looks happy with his stepson",
        "real madrid midfielder to attend barcelona pre season friendly in england",
        "barcelona pre season friendly in england",
        "barcelona pre-season friendly in england",

        # August 1: pundit columns, lifestyle filler and malformed social
        # attribution should not displace concrete club updates.
        "chelsea next transfer could give jose mourinho",
        "chelsea's next transfer could give jose mourinho",
        "trent alexander arnold 27 anos sobre su infancia",
        "jugaba ajedrez con mis hermanos",
        "ibai llanos",
        "chelsea pensioners policy",
        "gracias @mariocortegana", "thanks @mariocortegana", "r to @mariocortegana",

        # August 2: opinionated Vinicius clickbait and vague Camavinga framing
        # are not concrete club updates.
        "florentino perez has to sacrifice vinicius", "sacrifice vinicius jr",
        "learn from his real galactico mistake", "galactico mistake",
        "sinsentido camavinga", "el sinsentido de camavinga",
        "surprising camavinga case", "camavinga case",
        "xabi alonso on why he left real madrid and joined chelsea",
        "xabi alonso on his departure from real madrid and move to chelsea",
        "alonso heals real madrid scars to lead chelseas senior revolution",
        "alonso heals real madrid scars to lead chelsea's senior revolution",
        "xabi alonso no olvida su salida del real madrid",
        "otros rodris de jose mourinho", "otros rodris de josé mourinho",
        "todo lo que no viste en nuestro primer partido de pretemporada",
        "everything you did not see in our first pre season match",
        "everything you didn't see in our first pre-season match",
        "trophyless since 2024", "isnt the real reason they have been trophyless",
        "isn't the real reason they have been trophyless",
        "transfer roundup: chelsea sell trevoh chalobah",
        "bring the noise",
        "fulham 2026 27 season preview", "fulham 2026/27 season preview",
        "can new boss alvaro arbeloa get them over the line",
        "endrick offer they re unlikely to approve",
        "endrick offer they're unlikely to approve",
        "alineaciones jornada 1 laliga ea sports",
        "most overrated myth about real madrid",
        "the most overrated myth about real madrid just got debunked",
        "acuerdos publicitarios",
        "real madrid penso en luka vuskovic",
        "xabi alonso's first chelsea game",
        "first chelsea game was all about four forwards",
        "real leganes resultado partido 28 julio 2026",
        "leganes: resultado del partido 28 julio",
        "real leganes result match july 28 2026",
        "fulham va con todo por gonzalo",
        "fulham gonzalo oferton delantero",
        "удивительный случай камавинги",

        # August 4 late evening: unrelated Chelsea, celebrity and speculative
        # opinion pieces should not fill a Real Madrid digest.
        "the real reason why chelsea signed jordan henderson",
        "wedding ronaldo and georgina", "ronaldo and georgina wedding", "georgina's wedding",
        "свадьба роналду и джорджины",
        "ibrahima konate arrives at real madrid facing",

        # August 5 morning: market roundups and unnamed opinion features can
        # be rewritten into false transfer claims, while tennis is out of scope.
        "resumen mercado fichajes real madrid martes 4 agosto",
        "resumen del mercado de fichajes",
        "real madrid show their brains once again",
        "deals for gonzalo garcia and cesar palacios",
        "real madrid versatile attacker ready to fight for place",
        "rublev", "рублев", "упущенных матчболов",

        # August 5 daytime: SEO transfer hubs, broad league listings, lifestyle
        # and ungrounded squad speculation are not individual club updates.
        "fichajes real madrid 2026/27", "fichajes real madrid 2026 27",
        "real madrid midfielder fails to convince",
        "pretemporada laliga 2026", "lille piensa en cestero",
        "palco bd", "alton towers",

        # August 6: a Neymar dispute has no club angle, even if a feed summary
        # happens to contain a broad football keyword.
        "santos issued a statement amid criticism of neymar",
        "criticism of neymar by remo",

        # August 6 afternoon: Europe-wide lists, rival-only transfers and
        # player leisure features must not pad a club-specific digest.
        "six promoted teams to look out for in europe",
        "todas las equipaciones", "equipaciones de primera y segunda division",
        "chelsea boss xabi alonso wants ambitious martin zubimendi",
        "rincon donde desconecta raul asencio",

        # The late July 19 catch-up mixed generic World Cup coverage, lifestyle
        # snippets, and ungrounded transfer clickbait into the club digest.
        "argentina make 3 changes to lineup", "argentina makes 3 changes to lineup",
        "argentina 3 changes to lineup", "argentina 3 changes lineup",
        "espana domina al descanso", "spain dominate at half time", "spain dominates at half time",
        "a 120 million decision could haunt real madrid", "120 million decision could haunt",
        "vinicius estrena nuevo look", "vinicius unveils new look", "vinicius new look",
        "asencio se resiste a salir", "bloquearia llegada de bastoni",

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
        "a bernardo silva no le sienta bien el mundial", "bernardo silva desaparece mapa",
        "бернарду сильве не нравится чемпионат мира",
        "jhon cordoba", "john cordoba", "джон кордоба", "джона кордобы",
        "подробности по травме джона кордобы", "шансах сыграть на чм",
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
        "no seguirle en instagram", "seguirle en instagram", "tardo 10 horas en hacerlo",
        "tardó 10 horas en hacerlo", "dardo de courtois a cucurella",
        "queja de courtois", "courtois a cucurella", "instagram", "инстаграм",
        "ya no cree en el fichaje de este jugador", "no cree en el fichaje de este jugador",
        "больше не верит в трансфер этого игрока", "больше не верит в переход этого игрока",
        "трансфер этого игрока", "переход этого игрока",

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
        "jaime pradilla", "pradilla", "хайме прадилья", "прадилья",

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
        "carlo ancelotti has turned brazil", "brazil carlo ancelotti world cup",
        "turned brazil into potential world cup winner", "potential world cup winner",
        "карло анчелотти превратил бразилию", "бразилию в потенциальных победителей",
        "round 32 clash world cup", "японских интеллектуальных играх",
        "анчелотти отказывается участвовать", "интеллектуальных играх",
        "как формируется новая бразилия", "new brazil taking shape",
        "new brazil is taking shape", "how new brazil is taking shape",
        "cunha plays key role", "кунь", "кунья играет ключевую роль",
        "bonito reencuentro cristiano ronaldo rodrygo",
        "cristiano ronaldo rodrygo portugues preocupo lesion",
        "cristiano ronaldo delivers a clear message",
        "clear message to the football world",
        "message to the football world",
        "cristiano ronaldo went no lies detected",
        "no lies detected on portugal legacy",
        "portugal legacy with uncomfortable truth",
        "cristiano ronaldo y rodrygo", "reencuentro cristiano rodrygo",
        "reencuentro cristiano-rodrygo", "cristiano-rodrygo",
        "прекрасная встреча криштиану роналду и родриго",
        "криштиану роналду и родриго", "возвращение криштиану и родриго",
        "португалец беспокоился о своей травме",
        "криштиану роналду рассказал о своем португальском наследии",
        "португальском наследии",
        "croatia portugal luka modric cristiano ronaldo",
        "modric and cristiano ronaldo",
        "modric cristiano ronaldo world cup",
        "modric and ronaldo hope to avoid elimination",
        "world cup elimination",
        "icons modric ronaldo hope avoid elimination",
        "luka modric faces major career decision",
        "major career decision after world cup exit",
        "world cup exit as real madrid monitor",
        "real madrid monitor situation modric",
        "real madrid atento decision modric",
        "real madrid atento a decision modric",
        "real madrid atento a la decision modric",
        "real madrid atento a la decision de modric",
        "modric debe tomar una decision",
        "modric debe tomar una decisión",
        "иконы модрич и роналду",
        "модрич и роналду надеются избежать",
        "модрич должен принять решение",
        "карьерное решение после вылета с чемпионата мира",
        "реал в бегах",
        "избежать удаления с чемпионата",
        "ronaldo nazario", "ronaldo nazário", "mbappe recuerda mi prime",
        "mbappe me recuerda", "мбаппе напоминает мне меня", "роналду назарио: мбаппе",
        "роналду забыл о винисиусе", "забыл о винисиусе",
        "я не вижу другого такого, как неймар", "другого такого, как неймар",
        "fede valverde's uruguay eliminated", "uruguay eliminated from 2026 world cup",
        "fede valverde accepts responsibility", "accepts responsibility after uruguay",
        "uruguay's world cup exit", "uruguays world cup exit", "wasn't up to it",
        "wasn t up to it", "i know i wasn", "i know i was not",
        "uruguay eliminated", "uruguay knocked out", "valverde's uruguay",
        "сборная уругвая", "уругвая из-за феде вальверде", "вылетела с чемпионата мира",
        "феде вальверде берет на себя ответственность", "феде вальверде берёт на себя ответственность",
        "после вылета сборной уругвая", "я знаю, что был не готов",
        "spain clinch first place", "marc cucurella features in win over uruguay",
        "features in win over uruguay", "win over uruguay", "first place in their group",
        "испания завоевала первое место", "голу марка кукуреллы", "победу над уругваем",
        "cucurella vuela en el mundial", "madrid se frotan las manos",
        "кукурелла летит на чемпионат мира", "в мадриде потирают руки",
        "marc cucurella reflected every real madrid fan",
        "cucurella reflected every real madrid fan",
        "cucurellas spain knock out portugal",
        "cucurella's spain knock out portugal",
        "марк кукурелла отразил всех болельщиков",
        "сборная испании в составе марка кукуреллы",
        "real madrid protagonista en la tanda de penaltis", "tanda de penaltis del australia",
        "australia-egipto", "australia egipto", "австралия-египет",
        "bellingham 23 anos sobre lo que mas le gusta de espana", "para caminar por una gran ciudad",
        "bellingham became tuchel", "bellingham has become tuchel",
        "tuchel's most important player", "tuchel most important player",
        "most important player for tuchel", "important player tuchel",
        "беллингем стал важнейшим игроком тухеля", "важнейшим игроком тухеля",
        "what thomas tuchel did to trent", "tuchel did to trent",
        "trent alexander-arnold feels like a fireable offense", "fireable offense",
        "тухель сделал с трентом", "преступление, за которое можно уволить",
        "man united legends question tuchel", "tuchel's decision to omit real madrid superstar",
        "tuchel decision to omit real madrid superstar", "omit real madrid superstar", "head scratcher",
        "решение тухеля не вызвать", "не вызвать суперзвезду реала",
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
        "vinicius junior did not hold back after brazil",
        "brazil's inexcusable elimination", "brazils inexcusable elimination",
        "винисиус джуниор не сдержался", "непростительного удаления бразилии",
        "norway vs france", "haaland on bench", "senegal iraq", "senegal - iraq",
        "норвегии, но мбаппе", "сенегал - ирак", "сенегал — ирак",
        "francia gana", "france wins", "hat-trick ousmane", "ousmane dembele",
        "asistencias kylian", "mbappe solidario", "mbappé solidario",
        "solidario mejor mundial", "mejor mundial", "mejor del mundial",
        "paraguay france live", "paraguay - france", "paraguay-france",
        "france morocco live", "france - morocco", "france-morocco",
        "france morocco live stream", "live stream score result world cup quarter final",
        "olise appeal rejected", "appeal michael olise rejected", "appeal rejected by fifa",
        "atlas lions",
        "paraguay no pudo con mbappe", "paraguay no pudo con mbappé",
        "paraguay hates mbappe", "paraguay odia mbappe",
        "senadora celeste amenaza mbappe", "celeste amarilla comments",
        "colonized cameroonian", "colonizado camerunes",
        "сенатор селеста угрожает мбаппе", "парагвай не сломил мбаппе",
        "парагвай ненавидит мбаппе", "скандал между мбаппе и сенатором",
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
        "xabi alonso told why he decided to lead chelsea",
        "xabi alonso explains why he decided to take over chelsea",
        "nueva etapa asi luce xabi alonso", "nueva etapa así luce xabi alonso",
        "xabi alonso primer entrenamiento chelsea", "primer entrenamiento con el chelsea",
        "tope del real madrid con vini", "tope-real-madrid-vini-cambios-plan-mourinho-decision-clave-fichajes",
        "jude bellingham has ended a world cup debate", "ended a world cup debate that should",
        "jurgen klopp kylian mbappe liverpool talks private jet", "mbappe liverpool talks private jet",
        "liverpool talks on private jet", "talks on private jet psg transfer",
        "какие рекорды уже побил чм-2026", "месси, роналду и очоа",
        "real madrid presume cantera espana europeo sub-19", "real madrid presume cantera españa europeo sub-19",
        "jose luis sanchez compara bellingham con lamine", "compara bellingham con lamine",
        "comercios bernabeu market", "comercios bernabéu market", "bernabeu market levantan armas",
        "henderson breaks hand", "marc guehi receives blow",
        "ayyoub bouaddi sent an undeniable transfer guarantee", "undeniable transfer guarantee to real madrid",
        "nico paz cumple sueno chiquitito", "nico paz cumple sueño chiquitito",
        "lukaku pudo haber llegado real madrid", "lukaku pudo haber llegado al real madrid",
        "shakira", "shakira le da gracias mbappe", "shakira le da gracias a mbappe", "shakira le da gracias a mbappé", "shakira thanks mbappe",
        "claude makelele throws jude bellingham", "impassioned kylian mbappe defense",
        "habi alonso rasskazal pochemu on reshil vozglavit chelsi",
        "хаби алонсо рассказал, почему он решил возглавить челси",
        "хаби алонсо рассказал почему он решил возглавить челси",
        "возглавить челси",
        "juancho hernangomez", "juancho hernangómez", "хуанчо эрнангомес",
        "edu aguirre defiende cristiano", "menosprecia mundial michael olise",
        "лениво включать", "лень включать его в число 4 лучших игроков турнира",
        "google permite elegir medios favoritos", "medios favoritos", "любимые медиафайлы",
        "smiles & casualties", "smiles casualties", "moving on", "general/",
        "transfer market today", "mercado de fichajes hoy", "live transfer market",
        "real madrid transfer latest news", "latest real madrid transfer news",
        "fichajes real madrid ultimas noticias", "fichajes real madrid últimas noticias",
        "fichajes real madrid: ultimas noticias", "fichajes real madrid: últimas noticias",
        "fichajes real madrid | ultimas noticias", "fichajes real madrid | últimas noticias",
        "mercado fichajes real madrid", "mercado de fichajes real madrid",
        "ultimas noticias fichajes", "últimas noticias fichajes",
        "рынок трансферов сегодня", "в прямом эфире | последние новости",
        "lectores defensa central", "lectores", "aprueban forma masiva", "rechazan vender",
        "encuesta", "87%", "60%", "se opone", "palo de arda", "palo arda", "un palo",
        "anti-endrick", "anti endrick", "anti-endrik", "anti endrik",
        "4 champions eclipsan", "eclipsan eliminatoria seleccion", "ni 4 campeones", "ни 4 чемпиона",
        "so much for the endrick breakout", "endrick breakout under carlo ancelotti",
        "прорыв эндрика под руководством карло анчелотти",
        "secret laboratory ancelotti", "laboratorio secreto ancelotti",
        "transformacion genio", "transformación genio",
        "как анчелотти переворачивает матчи чм",
        "секретная лаборатория анчелотти", "поиск пути к гекса",
        "ex madrid destripa ancelotti", "basta vergueenza", "basta vergüenza",
        "бывший игрок мадрида выпотрошил анчелотти",
        "бывший игрок «мадрида» выпотрошил анчелотти",
        "выпотрошил анчелотти",
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
        "genich", "spertsyan", "сперцян", "генич",
        "ex madrid gente comia poco", "gente comia poco", "chavales comiamos",
        "бывший житель мадрида", "люди ели очень мало", "спагетти с помидорами",
        "gareth bale 36 anos", "jugue 13 anos con luka modric",
        "гарет бэйл", "я играл за луку модрича",
        "keane and gerrard shadows", "rooney on bellingham",
        "тени кина и джеррарда", "руни",
        "minimum one player in final mundial", "menos jugador en final mundial",
        "cuando juegan jugadores real madrid cuartos mundial",
        "cuando juegan los jugadores del real madrid en cuartos",
        "jugadores real madrid cuartos mundial",
        "real madrid players quarter finals world cup",
        "real madrid players world cup quarter finals",
        "siro lopez", "siro lópez", "me he encontrado en estados unidos",
        "nueva vida en espana con bernardo silva", "nueva vida en españa con bernardo silva",
        "минимум одного игрока в финале чемпионата мира",
        "getting the neymar treatment", "курс лечения у неймара",
        "cambio apuestan madridistas", "перемены, на которые делают ставку",
        "nobody saw coming", "transfer decision nobody saw coming",
        "unexpected transfer decision", "неожиданное трансферное решение",
        "mourinho just made a real madrid transfer decision",
        "barcelona copies real madrid",
        "desesperada firmar julian alvarez",
        "desesperada por firmar julian alvarez",
        "хулиана маньяра альвареса",
        "atletico pesca talento fabrica alvaro vega",
        "atletico pesca talento la fabrica",
        "alvaro vega refuerza juvenil",
        "alvaro vega",
        "атлетико ловит талантливых игроков на заводе",
        "атлетико ловит талантов на фабрике",
        "rincon donde desconecta luka modric", "rincón donde desconecta luka modric",
        "comer carne a la brasa", "7 minutos del estadio santiago bernabeu",

        # August 7: pundit speculation, generic market roundups and lifestyle
        # posts should not dilute the matchday or confirmed club news.
        "franco mastantuono 19 anos sobre su infancia", "dejar mi casa tan pronto me hizo madurar",
        "tranquilidad definitiva vini nervios totales centro campo",
        "ni interior ni extremo derecho mourinho ve mastantuono",
        "ideal starting midfield trio",
        "mbappe machaca ibiza", "mbappe trains in ibiza",
        "why arsenal move for chelsea's josh acheampong",
        "confirmado nueva sede supercopa espana 2027",
        "decision rodri retomada operacion central",
        "madrid no llora a rodri", "respuesta roncero al no de rodri",

        # August 8-9: personal anecdotes, generic opinion pieces and rival-only
        # stories leaked into the first matchday run and weekly recap.
        "the real madrid trio jose mourinho can t trust",
        "the real madrid trio jose mourinho can't trust",
        "endrick 20 anos sobre su padre", "endrick 20 años sobre su padre", "endrick 20 on his father",
        "endrick, 20, on his father",
        "endrick's father", "father of endrick", "chicharito", "jose hernandez balcarcel",
        "what does next years midfield look like", "what does next year's midfield look like",
        "jeno kalmar", "jeno kálmár", "man united psg live", "man united vs psg",
        "liverpool want ronald araujo", "ronald araujo loan to liverpool",
        "tchouameni 26 anos sobre su infancia", "tchouameni 26 años sobre su infancia",
        "мбаппе тренируется на ибице", "мбаппе готовится на ибице",

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
    "x - @realmadrid",
    "x – @realmadrid",
    "x - @realmadriden",
    "x – @realmadriden",
    "x - @mariocortegana",
    "x – @mariocortegana",
    "x - @aranchamobile",
    "x – @aranchamobile",
    "x - @melchorcope",
    "x – @melchorcope",
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

RIVAL_ONLY_MARKERS = (
    "atletico", "atlético", "атлетико", "барселона", "barcelona", "chelsea", "челси",
    "arsenal", "арсенал", "liverpool", "ливерпуль", "bayern", "бавария", "psg", "псж",
    "juventus", "ювентус", "milan", "милан", "inter", "интер", "napoli", "наполи",
    "tottenham", "тоттенхэм", "manchester city", "манчестер сити", "ман сити", "newcastle", "ньюкасл",
    "fiorentina", "фиорентина", "parma", "парма",
)
DIRECT_REAL_MARKERS = (
    "real madrid", "реал мадрид", "rmcf", "los blancos", "la fabrica", "la fábrica", "фабрика", "castilla", "кастилья",
    "vinicius", "винисиус", "rodrygo", "родриго", "mbappe", "mbappé", "мбаппе", "bellingham", "беллингем", "endrick", "эндрик",
    "gonzalo garcia", "гонсало гарсия", "nico paz", "нико пас", "mastantuono", "мастантуоно", "arda guler", "arda güler", "арда гюлер",
    "valverde", "вальверде", "tchouameni", "tchouaméni", "тчуамени", "camavinga", "камавинга", "modric", "modrić", "модрич", "kroos", "кроос",
    "ceballos", "себальос", "brahim", "брахим", "courtois", "куртуа", "lunin", "лунин", "militao", "militão", "милитао", "rudiger", "rüdiger", "рюдигер",
    "carvajal", "карвахаль", "trent", "трент", "huijsen", "хуисен", "asencio", "асенсио", "mendy", "менди", "fran garcia", "фран гарсия",
    "carreras", "каррерас", "olise", "олисе", "konate", "konaté", "конате", "bernardo silva", "бернарду сильва",
    "cucurella", "кукурелья", "carlos espi", "карлос эспи", "mourinho", "моуринью", "florentino perez", "florentino pérez", "флорентино перес",
)

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


def _matches_direct_real_marker(text: str) -> bool:
    """Match club people as whole words so one surname cannot match another."""
    title = _normalize(text)
    return any(
        re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", title)
        for marker in DIRECT_REAL_MARKERS
    )


def is_off_topic_whitelist_headline(text: str, source: str = "") -> bool:
    """Require a direct Madrid subject when a broad football source hits a name keyword."""
    title = _normalize(text)
    source_name = _normalize(source)
    return bool(
        source_name
        and not _matches_any(source_name, _REAL_SOURCE_MARKERS)
        and _matches_any(title, _WHITELIST)
        and not _matches_direct_real_marker(title)
    )


def _real_source_has_topic_signal(title: str, body: str) -> bool:
    """A Real-only feed still needs a concrete Madrid subject in its headline."""
    return (
        _matches_any(title, _WHITELIST)
        or (
            _matches_any(title, _REAL_SOURCE_TOPIC_MARKERS)
            and _matches_direct_real_marker(title)
        )
    )


def is_handle_only_x_title(text: str, source: str = "") -> bool:
    """Reject social cards that contain only tagged accounts, not a news headline."""
    plain = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", str(text or "")).strip()
    return bool(re.fullmatch(r"(?:@[\w]+\s*)+", plain))


def is_name_only_x_title(text: str, source: str = "") -> bool:
    """Reject social cards that contain only a person's name without an update."""
    source_name = _normalize(source)
    if not source_name.startswith("x - @"):
        return False
    plain = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", str(text or "")).strip()
    return bool(re.fullmatch(r"[^\W\d_]+(?:\s+[^\W\d_]+){0,2}", plain, flags=re.UNICODE))


def is_low_signal_x_question(text: str, source: str = "") -> bool:
    """Reject bare reporter questions that offer no actual update to readers."""
    source_name = _normalize(source)
    if not source_name.startswith("x - @"):
        return False
    plain = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", str(text or "")).strip()
    if not plain.endswith(("?", "؟")):
        return False
    return len(re.findall(r"\w+", plain)) <= 10


def is_truncated_x_title(text: str, source: str = "") -> bool:
    """Reject clipped social snippets that still contain a source URL."""
    source_name = _normalize(source)
    plain = str(text or "").strip()
    return (
        source_name.startswith("x - @")
        and ("http://" in plain or "https://" in plain)
        and (plain.endswith("...") or plain.endswith("…"))
    )


def is_managing_madrid_dated_general_thread(text: str, source: str = "", link: str = "") -> bool:
    """Reject the source's dated /general/ discussion threads from news selection."""
    if _normalize(source) != "managing madrid" or "/general/" not in str(link or "").casefold():
        return False
    plain = _normalize(text)
    months = (
        "january|february|march|april|may|june|july|august|september|"
        "october|november|december"
    )
    return bool(re.search(rf"\b\d{{1,2}}\s+(?:{months})\s+20\d{{2}}\b", plain))


def is_non_football_sports_link(link: str = "") -> bool:
    """Reject broad-sports feed entries by their canonical URL section."""
    lower_link = str(link or "").casefold()
    return any(
        f"/{sport}/" in lower_link
        for sport in ("cricket", "tennis", "rugby", "golf", "boxing", "mma", "ufc", "motorsport")
    )


def is_promotional_link(link: str = "") -> bool:
    """Reject commercial or game-promotion pages that merely mention football."""
    lower_link = str(link or "").casefold()
    return "/fantasy/" in lower_link or "utm_campaign=fantasy" in lower_link


def is_editorial_analysis_link(text: str, link: str = "") -> bool:
    """Keep reports, not generic observation columns or post-match listicles."""
    title = _normalize(text)
    lower_link = str(link or "").casefold()
    return bool(
        "managingmadrid.com/kiyans-observations/" in lower_link
        or any(marker in title for marker in ("five bullet points from", "burning questions from"))
    )


def is_low_value_feature(text: str) -> bool:
    """Reject personal anecdotes, stale controversy and unsupported opinion hooks."""
    title = _normalize(text)
    domestic_clickbait = (
        any(marker in title for marker in ("climatizacion", "aire acondicionado"))
        and any(marker in title for marker in ("piscina", "casa", "mando", "boton", "button", "remote"))
    )
    pundit_transfer_opinion = (
        "michael owen" in title
        and "haaland" in title
        and "real madrid" in title
    )
    courtois_school_anecdote = "courtois" in title and "madre" in title and "colegio" in title
    mendes_zubimendi_teaser = all(marker in title for marker in ("jorge mendes", "zubimendi", "sorpresa"))
    family_profile = (
        any(marker in title for marker in ("mother of", "father of", "madre de", "padre de"))
        and any(marker in title for marker in ("anos", "años", "years old"))
    )
    family_lifestyle_profile = (
        any(marker in title for marker in ("mother", "father", "brother", "sister", "madre", "padre", "hermano", "hermana"))
        and any(marker in title for marker in ("clean", "limpieza", "desorden", "childhood", "infancia", "home", "house", "casa"))
    )
    external_historical_comparison = (
        "real madrid" in title
        and (
            "luis enrique" in title
            or "psg manager" in title
        )
        and any(marker in title for marker in ("three-peat", "three champions", "3 champions", "tres champions"))
    )
    generic_editorial_noise = any(
        marker in title
        for marker in (
            "unbreakable champions league record",
            "luis enrique pone madrid en el punto de mira",
            "miguel munoz le dio al madrid la primera teresa herrera",
        )
    )
    luis_enrique_psg_hook = (
        "luis enrique" in title
        and "psg" in title
        and ("real madrid" in title or "madrid" in title)
    )
    modric_replacement_hook = (
        "modric" in title
        and "replacement" in title
        and any(marker in title for marker in ("finally have", "finally found", "al fin tiene"))
    )
    relationship_editorial = (
        "mourinho" in title
        and "bellingham" in title
        and any(
            marker in title
            for marker in (
                "condenados a entenderse",
                "must find common ground",
                "need to find common ground",
                "should find common ground",
            )
        )
    )
    aubameyang_depor_feature = "aubameyang" in title and "depor" in title
    personal_qa = any(
        marker in title
        for marker in (
            "hidden talent",
            "talento oculto",
            "favorite food",
            "favourite food",
            "comida favorita",
            "favorite singer",
            "favourite singer",
            "cantante favorito",
        )
    )
    personal_markers = (
        "sobre su infancia",
        "on his childhood",
        "sobre su padre",
        "on his father",
        "о своем детстве",
        "о своём детстве",
    )
    clickbait_opinions = (
        "best possible destination away from real madrid",
        "real madrid necesita jugadores",
        "pista real madrid endrick apunta continuidad",
        "mercado fichajes: sorpreson final",
        "el madrid que viene",
        "three best loan destinations for endrick",
        "реалу нужно больше игроков",
    )
    return bool(
        "eva carneiro" in title
        or any(marker in title for marker in personal_markers)
        or any(marker in title for marker in clickbait_opinions)
        or domestic_clickbait
        or pundit_transfer_opinion
        or courtois_school_anecdote
        or mendes_zubimendi_teaser
        or family_profile
        or family_lifestyle_profile
        or external_historical_comparison
        or generic_editorial_noise
        or luis_enrique_psg_hook
        or modric_replacement_hook
        or relationship_editorial
        or aubameyang_depor_feature
        or personal_qa
    )


def is_vague_status_headline(text: str) -> bool:
    """Reject anonymous status reports and non-updates about a named player."""
    title = _normalize(text)
    anonymous_status = re.search(
        r"\b(?:real madrid )?(?:midfielder|defender|forward|player|star)\b.*"
        r"\b(?:will stay|important role|amid uncertainty)\b",
        title,
    )
    anonymous_hierarchy = re.search(
        r"\b(?:mourinho|manager|coach)\b.*\b(?:informs?|tells?|sets?)\b.*"
        r"\b(?:real madrid )?(?:midfielder|defender|forward|player|star)\b.*"
        r"\b(?:pecking order|hierarchy|where exactly he stands|where he stands)\b",
        title,
    )
    anonymous_exit = re.search(
        r"\breal madrid\b.*\b(?:another|one more)\s+(?:talented )?"
        r"(?:player|youngster|talent|prodigy)\b.*\b(?:leave|exit|loan|transfer)\b",
        title,
    )
    anonymous_academy_move = re.search(
        r"\breal madrid\b.*\b(?:youth\s+)?(?:prodigy|prospect|talent|youngster|academy player)\b.*"
        r"\b(?:potential move|potential transfer|move .* falls through|transfer .* falls through|on the verge|close to|record move)\b",
        title,
    )
    return bool(
        anonymous_status
        or anonymous_hierarchy
        or anonymous_exit
        or anonymous_academy_move
        or "no despeja dudas" in title
        or "не развеивает сомнения" in title
    )


def is_rival_only_headline(text: str) -> bool:
    """Reject rival-only facts even when a Real-focused source republishes them."""
    title = _normalize(text)
    return bool(
        _matches_any(title, RIVAL_ONLY_MARKERS)
        and not _matches_direct_real_marker(title)
    )


def is_unnamed_real_madrid_link_headline(text: str) -> bool:
    """Reject transfer bait that never names the player or a concrete club action."""
    title = _normalize(text)
    direct_link_bait = re.search(
            r"(?:real madrid[- ]linked|linked with real madrid|vinculado al real madrid)"
            r"\s+(?:midfielder|defender|forward|player|star)",
            title,
    )
    unnamed_denial = re.search(
        r"\breal madrid(?:'s)? links? to (?:an? )?(?:[a-z]+ )?"
        r"(?:midfielder|defender|forward|player|star)\b.*\b(?:no basis|no foundation|baseless)\b",
        title,
    )
    return bool(direct_link_bait or unnamed_denial)


def is_speculative_editorial_headline(text: str) -> bool:
    """Reject opinion hooks that frame a hypothetical career narrative as news."""
    title = _normalize(text)
    return bool(
        (
            "could hand" in title
            and "career" in title
            and ("real madrid" in title or _matches_direct_real_marker(title))
        )
        or (
            "reacted to" in title
            and any(marker in title for marker in ("super cup", "supercopa", "psg"))
        )
    )


def is_promotional_x_post(text: str, source: str) -> bool:
    """Keep official news, but skip promo links to long-form club content."""
    source_name = _normalize(source)
    if not source_name.startswith("x - @realmadrid"):
        return False

    title = _normalize(text)
    return any(
        marker in title
        for marker in (
            "full interview",
            "full video",
            "watch the full",
            "rm play",
            "entrevista completa",
            "video completo",
        )
    )


def is_unnamed_official_x_highlight(text: str, source: str) -> bool:
    """Skip generic highlight clips without a player or concrete club fact."""
    source_name = _normalize(source)
    if not source_name.startswith("x - @realmadrid"):
        return False

    title = _normalize(text)
    if _matches_direct_real_marker(title):
        return False
    return bool(
        re.search(
            r"\b(?:assist|asistencia)\b.{0,35}\b(?:perfect|perfecta|perfecto)\b.{0,35}"
            r"\b(?:finish|definition|definicion)\b",
            title,
        )
    )


def is_generic_official_x_training_post(text: str, source: str) -> bool:
    """Training photos belong to the visual rubric, not a text digest."""
    source_name = _normalize(source)
    if not source_name.startswith("x - @realmadrid"):
        return False
    title = _normalize(text)
    return title.startswith(("training day with", "day of training with", "dia de entrenamiento con"))


def is_off_topic_reporter_x_post(text: str, source: str) -> bool:
    """Reporter feeds are useful only when the post itself names a Madrid subject."""
    source_name = _normalize(source)
    if not source_name.startswith("x - @") or source_name.startswith("x - @realmadrid"):
        return False
    return not _matches_direct_real_marker(text)


def is_generic_competition_logistics(text: str) -> bool:
    """Skip tournament administration unless the title directly concerns Real."""
    title = _normalize(text)
    if _matches_direct_real_marker(title):
        return False
    return bool(
        any(marker in title for marker in ("spanish super cup", "supercopa de espana", "supercopa espana"))
        and any(marker in title for marker in ("new home", "new host", "new venue", "nueva sede", "new location"))
    )


def passes_filters(
    text: str,
    summary: Optional[str] = None,
    source: Optional[str] = None,
    link: Optional[str] = None,
) -> bool:
    """
    Основной фильтр релевантности.
    :param text: заголовок/лид
    :param summary: опционально — подводка/анонс
    :param source: опционально — бренд источника. Профильные источники Real Madrid проходят мягче.
    :param link: ссылка на материал. Нужна для отсечения служебных тредов источника.
    """
    if not text:
        logger.info("[FILTERED: EMPTY]")
        return False

    if is_duplicate(text):
        return False

    title = _normalize(text)
    body = _normalize(summary) if summary else ""
    source_name = _normalize(source) if source else ""

    if is_handle_only_x_title(text, source):
        logger.info(f"[FILTERED: X HANDLE ONLY] {source}: {text[:90]}...")
        return False

    if is_name_only_x_title(text, source):
        logger.info(f"[FILTERED: X NAME ONLY] {source}: {text[:90]}...")
        return False

    if is_low_signal_x_question(text, source):
        logger.info(f"[FILTERED: X QUESTION LOW SIGNAL] {source}: {text[:90]}...")
        return False

    if is_truncated_x_title(text, source):
        logger.info(f"[FILTERED: X TRUNCATED] {source}: {text[:90]}...")
        return False

    if is_managing_madrid_dated_general_thread(text, source, link):
        logger.info(f"[FILTERED: MANAGING MADRID GENERAL THREAD] {text[:90]}...")
        return False

    if is_non_football_sports_link(link):
        logger.info(f"[FILTERED: NON-FOOTBALL URL] {text[:90]}...")
        return False

    if is_promotional_link(link):
        logger.info(f"[FILTERED: PROMOTIONAL LINK] {text[:90]}...")
        return False

    if is_editorial_analysis_link(text, link):
        logger.info(f"[FILTERED: EDITORIAL ANALYSIS] {text[:90]}...")
        return False

    if is_low_value_feature(text):
        logger.info(f"[FILTERED: LOW-VALUE FEATURE] {text[:90]}...")
        return False

    if is_vague_status_headline(text):
        logger.info(f"[FILTERED: VAGUE STATUS] {text[:90]}...")
        return False

    if is_rival_only_headline(text):
        logger.info(f"[FILTERED: RIVAL ONLY] {text[:90]}...")
        return False

    if is_unnamed_real_madrid_link_headline(text):
        logger.info(f"[FILTERED: UNNAMED REAL LINK] {text[:90]}...")
        return False

    if is_speculative_editorial_headline(text):
        logger.info(f"[FILTERED: SPECULATIVE EDITORIAL] {text[:90]}...")
        return False

    if is_promotional_x_post(text, source):
        logger.info(f"[FILTERED: PROMOTIONAL X POST] {text[:90]}...")
        return False

    if is_unnamed_official_x_highlight(text, source):
        logger.info(f"[FILTERED: UNNAMED OFFICIAL X HIGHLIGHT] {text[:90]}...")
        return False

    if is_generic_official_x_training_post(text, source):
        logger.info(f"[FILTERED: GENERIC OFFICIAL X TRAINING] {text[:90]}...")
        return False

    if is_off_topic_reporter_x_post(text, source):
        logger.info(f"[FILTERED: OFF-TOPIC REPORTER X] {text[:90]}...")
        return False

    if is_generic_competition_logistics(text):
        logger.info(f"[FILTERED: GENERIC COMPETITION LOGISTICS] {text[:90]}...")
        return False

    if is_off_topic_whitelist_headline(text, source):
        logger.info(f"[FILTERED: WHITELIST WITHOUT DIRECT REAL] {source}: {text[:90]}...")
        return False

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

    if _matches_any(title, _WHITELIST):
        if _matches_direct_real_marker(title):
            logger.info(f"[PASSED: WHITELIST+DIRECT REAL] {text[:90]}...")
            return True
        logger.info(f"[FILTERED: WHITELIST WITHOUT DIRECT REAL] {text[:90]}...")
        return False

    if _matches_any(title, _GREYLIST):
        if "real madrid" in title or "реал" in title:
            logger.info(f"[PASSED: GREYLIST+REAL] {text[:90]}...")
            return True
        logger.info(f"[FILTERED: GREYLIST w/o REAL] {text[:90]}...")
        return False

    logger.info(f"[FILTERED: NO MATCH] {text[:90]}...")
    return False


def filter_news(
    text: str,
    summary: Optional[str] = None,
    source: Optional[str] = None,
    link: Optional[str] = None,
) -> bool:
    """
    Обёртка для совместимости. Старые вызовы с одним аргументом продолжают работать.
    """
    return passes_filters(text, summary=summary, source=source, link=link)
