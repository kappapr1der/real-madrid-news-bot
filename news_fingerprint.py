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

UCL_DRAW_TERMS = (
    "champions league draw",
    "champions league opponents",
    "league phase draw",
    "sorteo champions",
    "sorteo de champions",
    "sorteo de la champions",
    "жеребьевк",
    "соперник",
    "оппонент",
)
UCL_TERMS = ("champions league", "champions", "лига чемпионов", "лч")


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


def contains_alias(text: str, alias: str) -> bool:
    return re.search(rf"(?<![a-zа-я0-9]){re.escape(alias)}(?![a-zа-я0-9])", text) is not None


def ucl_draw_event_key(title: str, summary: str = "", event_date: str = "") -> str:
    """Return a stable key for the published UCL league-phase draw result."""
    if not event_date:
        return ""
    text = normalize_news_text(f"{title} {summary}")
    has_real = "real madrid" in text or "реал мадрид" in text
    if has_real and contains_any(text, UCL_TERMS) and contains_any(text, UCL_DRAW_TERMS):
        return f"event:ucl-draw:{event_date}"
    return ""


def player_key(text: str) -> str | None:
    for key, aliases in PLAYER_ALIASES.items():
        if any(contains_alias(text, alias) for alias in aliases):
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


def is_laliga_harassment_protocol_text(text: str) -> bool:
    return (
        contains_any(text, ("laliga", "la liga", "лига", "лиги"))
        and contains_any(text, ("protocolo", "protocol", "протокол"))
        and contains_any(text, ("acoso sexual", "sexual harassment", "домогательств"))
        and contains_any(
            text,
            (
                "tribunal",
                "court",
                "judicial",
                "rechaza",
                "reves",
                "revés",
                "suspender",
                "suspension",
                "суд",
                "юридичес",
                "отклонил",
                "приостанов",
            ),
        )
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


def is_raul_asencio_preseason_injury_text(text: str) -> bool:
    """Unify reports about Raul Asencio's six-week pre-season muscle injury."""
    named_report = (
        contains_any(text, ("raul asencio", "asencio", "асенсио"))
        and contains_any(text, ("injury", "injured", "muscle", "lesion", "lesionado", "out", "травм", "мышеч"))
        and contains_any(text, ("six weeks", "seis semanas", "preseason", "pre season", "pretemporada", "выбыл"))
    )
    unnamed_variant = contains_any(
        text,
        (
            "real madrid suffers muscle injury in pre season out for six weeks",
            "real madrid suffer muscle injury in pre season out for six weeks",
            "real madrid suffers muscle injury in preseason out for six weeks",
        ),
    )
    return named_report or unnamed_variant


def is_gonzalo_fulham_transfer_text(text: str) -> bool:
    """Collapse reports about Gonzalo's proposed Fulham transfer."""
    named_report = (
        contains_any(text, ("gonzalo", "гонсало"))
        and contains_any(text, ("fulham", "фулхэм"))
        and contains_any(
            text,
            (
                "transfer",
                "sale",
                "sell",
                "join",
                "joins",
                "fichaje",
                "traspaso",
                "venta",
                "переход",
                "продаж",
            ),
        )
    )
    full_ownership_variant = (
        contains_any(text, ("fulham", "фулхэм"))
        and contains_any(text, ("full ownership", "ownership", "propiedad", "выкуп"))
        and contains_any(text, ("60 million", "60m", "60 millones", "60 миллионов"))
    )
    departure_followup = (
        contains_any(text, ("gonzalo", "гонсало"))
        and contains_any(text, ("mourinho", "моуринью"))
        and contains_any(
            text,
            (
                "leave",
                "leaves",
                "left",
                "departure",
                "exit",
                "salida",
                "se marcha",
                "marcha",
                "marcho",
                "покинул",
                "ушел",
                "уход",
            ),
        )
    )
    return named_report or full_ownership_variant or departure_followup


def is_medical_staff_changes_text(text: str) -> bool:
    return (
        contains_any(
            text,
            (
                "medical staff",
                "medical team",
                "medicinsk",
                "medico",
                "medicos",
                "медицин",
                "медштаб",
                "мед штаб",
                "shtab",
                "штаб",
            ),
        )
        and contains_any(
            text,
            (
                "change",
                "changes",
                "sweeping",
                "rebuild",
                "restruct",
                "cambios",
                "reestruct",
                "perestra",
                "перестра",
                "меняет",
                "измен",
            ),
        )
        and contains_any(text, ("injury", "injuries", "injury plagued", "lesion", "lesiones", "travm", "травм", "mbappe", "мбаппе"))
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
        contains_any(text, ("laporta", "лапорта", "barcelona president", "president barcelona", "президент барселоны"))
        and contains_any(text, ("real madrid", "florentino", "реал", "флорентино"))
        and contains_any(
            text,
            (
                "attacks",
                "takes aim",
                "hits back",
                "hit back",
                "critica",
                "critico",
                "critic",
                "ataca",
                "dispara",
                "deja vu",
                "ответный удар",
                "нанес ответ",
                "критик",
                "атак",
            ),
        )
    )


def is_camavinga_manchester_city_text(text: str) -> bool:
    return (
        contains_any(
            text,
            (
                "camavinga",
                "камавинг",
                "23 year old midfielder",
                "23 летнего полузащитника",
                "23 летний полузащитник",
                "23 летним полузащитником",
            ),
        )
        and contains_any(text, ("manchester city", "man city", "city", "сити", "premier", "премьер", "апл"))
        and contains_any(
            text,
            (
                "offer",
                "ofrece",
                "offered",
                "discuss",
                "talk",
                "contact",
                "option",
                "deal",
                "transfer",
                "move",
                "предлага",
                "обсужд",
                "сделк",
                "контакт",
                "опци",
                "вариант",
                "переход",
                "трансфер",
            ),
        )
    )


def is_valverde_stays_real_text(text: str) -> bool:
    if not contains_any(text, ("valverde", "вальверде")):
        return False
    if not contains_any(text, ("real madrid", "madrid", "реал", "мадрид")):
        return False
    return (
        contains_any(text, ("firme", "firm at", "firm in", "firm with", "firmly", "твёрд", "тверд"))
        or (
            contains_any(text, ("destino", "future", "futuro", "будущ"))
            and contains_any(text, ("confirmado", "confirmed", "confirma", "подтвержд"))
        )
        or (
            contains_any(text, ("continuara", "continua", "seguira", "se queda", "stays", "stay", "остает", "остан"))
            and not contains_any(text, ("uruguay", "уругвай"))
        )
    )


def is_modric_career_decision_noise_text(text: str) -> bool:
    if not contains_any(text, ("luka modric", "modric", "модрич")):
        return False
    if not contains_any(text, ("decision", "decisión", "career", "carrera", "решени", "карьер")):
        return False
    return (
        contains_any(text, ("world cup exit", "mundial", "championship", "чемпионат", "вылет", "elimin"))
        or contains_any(text, ("real madrid monitor", "real madrid atento", "real atento", "следит", "в бегах"))
    )


def is_enzo_denial_text(text: str) -> bool:
    return contains_any(text, ("enzo fernandez", "enzo fernández", "энцо фернандес")) and contains_any(
        text,
        (
            "no plan",
            "no planning",
            "not plan",
            "not planning",
            "do not plan",
            "not sign",
            "no sign",
            "no fich",
            "no firm",
            "desmiente",
            "deny",
            "denies",
            "ruling out",
            "no tiene ninguna intencion",
            "no tiene ninguna intención",
            "no negoc",
            "not negotiating",
            "no estaba negociando",
            "anunciando que no estaba negociando",
            "comunicados oficiales",
            "reality check",
            "опроверг",
            "не планирует подпис",
            "не подпиш",
            "не ведет переговор",
            "не ведёт переговор",
        ),
    )


def is_vinicius_renewal_text(text: str) -> bool:
    return (
        contains_any(text, ("vinicius", "vini", "винисиус", "вини джуниор"))
        and contains_any(
            text,
            (
                "renew",
                "renovar",
                "renovacion",
                "renovación",
                "contract",
                "contrato",
                "продлен",
                "контракт",
                "future",
                "futuro",
                "talks",
                "conversation",
                "conversaciones",
                "переговор",
                "будущ",
                "arsenal",
                "арсенал",
            ),
        )
    )


def is_tchouameni_extension_text(text: str) -> bool:
    has_tchouameni = contains_any(text, ("tchouameni", "tchouaméni", "тчуамени", "чуамени"))
    has_tchouameni_hint = (
        contains_any(text, ("midfield mainstay", "mainstay", "основн"))
        and contains_any(text, ("manchester united", "united", "манчестер"))
    )
    return (
        (has_tchouameni or has_tchouameni_hint)
        and contains_any(text, ("extend", "extension", "renew", "renovacion", "renovación", "contract", "contrato", "продл", "продление", "контракт"))
        and contains_any(text, ("2031", "real madrid", "madrid", "реал", "мадрид"))
    )


def is_player_sales_revenue_text(text: str) -> bool:
    return (
        contains_any(text, ("real madrid", "madrid", "реал", "мадрид", "la fabrica", "fabrica", "фабрика", "gila", "хила"))
        and contains_any(
            text,
            (
                "sales",
                "sale",
                "ventas",
                "venta",
                "revenue",
                "windfall",
                "recaudar",
                "ingres",
                "embols",
                "financia",
                "million",
                "millon",
                "millones",
                "kilos",
                "млн",
                "миллион",
                "продаж",
                "доход",
                "заработ",
                "финанс",
            ),
        )
        and contains_any(text, ("academy", "cantera", "la fabrica", "fabrica", "фабрик", "gila", "хила", "ventas", "sales", "продаж"))
    )


def is_laliga_opener_postponed_text(text: str) -> bool:
    return (
        contains_any(text, ("laliga", "la liga", "liga", "лиги", "лалига", "лига"))
        and contains_any(text, ("opener", "debut", "first match", "primer partido", "debut liguero", "inicio", "старт", "первый матч", "дебют", "открытие"))
        and contains_any(text, ("postpon", "aplaz", "atrasa", "delay", "перенес", "перенос", "отлож", "отсроч"))
        and contains_any(text, ("real madrid", "madrid", "реал", "мадрид", "real sociedad", "сосьедад", "bernabeu", "бернабеу"))
    )


def is_teresa_herrera_deportivo_text(text: str) -> bool:
    return (
        contains_any(text, ("teresa herrera", "trofeo teresa", "teresa herrera trophy"))
        and contains_any(text, ("deportivo", "la coruna", "la coruña"))
        and contains_any(text, ("friendly", "amistoso", "pre season", "pre-season", "preseason", "pretemporada", "debut", "face", "contra"))
    )


def is_fiorentina_austria_friendly_text(text: str) -> bool:
    return (
        contains_any(text, ("fiorentina", "фиорентин"))
        and contains_any(text, ("real madrid", "реал"))
        and contains_any(
            text,
            (
                "austria",
                "австри",
                "august",
                "agosto",
                "1 de agosto",
                "friendly",
                "amistoso",
                "pre season",
                "pre-season",
                "preseason",
                "pretemporada",
                "match",
                "partido",
            ),
        )
    )


def is_schalke_preseason_friendly_text(text: str) -> bool:
    """Collapse all reports about Real Madrid's pre-season friendly with Schalke 04."""
    return (
        contains_any(text, ("schalke", "schalke 04", "шальке"))
        and contains_any(text, ("real madrid", "madrid", "реал"))
    )


def is_mastantuono_river_loan_text(text: str) -> bool:
    """Unify Mastantuono's reported loan preference to return to River Plate."""
    named_report = (
        contains_any(text, ("mastantuono", "мастантуоно"))
        and contains_any(text, ("river plate", "river", "ривер плейт", "ривер"))
        and contains_any(
            text,
            ("loan", "on loan", "cedido", "cesion", "cesión", "river plate", "return", "volver", "аренд", "вернут"),
        )
    )
    unnamed_variant = (
        contains_any(text, ("teenage wonderkid", "teenage prodigy", "teenage star", "подросток"))
        and contains_any(text, ("loan", "on loan", "cedido", "cesion", "cesión", "аренд"))
        and contains_any(text, ("former club", "rejoin", "return", "volver", "бывший клуб", "вернуться"))
    )
    return named_report or unnamed_variant


def is_mastantuono_roma_transfer_text(text: str) -> bool:
    """Collapse the current Roma interest in Mastantuono."""
    return (
        contains_any(text, ("mastantuono", "мастантуоно"))
        and contains_any(text, ("roma", "роме", "рома"))
        and contains_any(
            text,
            (
                "transfer",
                "loan",
                "sign",
                "signing",
                "talk",
                "talks",
                "negotiat",
                "offer",
                "offers",
                "interest",
                "interested",
                "fichaje",
                "negoci",
                "oferta",
                "interes",
                "cedido",
                "cesion",
            ),
        )
    )


def is_fulham_palacios_garcia_text(text: str) -> bool:
    """Group the Fulham thread concerning Cesar Palacios and Garcia."""
    named_report = (
        contains_any(text, ("fulham", "фулхэм"))
        and contains_any(text, ("cesar palacios", "césar palacios", "palacios", "сесар паласиос"))
    )
    unnamed_variant = contains_any(
        text,
        (
            "premier league club in direct talks with real madrid over 21 year old academy gems transfer",
            "premier leauge club in direct talks with real madrid over 21 year old academy gems transfer",
        ),
    )
    return named_report or unnamed_variant


def is_haaland_family_real_text(text: str) -> bool:
    return (
        contains_any(text, ("haaland", "haaland", "холанд", "хааланд"))
        and contains_any(text, ("father", "padre", "clan", "семья", "отец", "клан", "bombazo"))
        and contains_any(text, ("real madrid", "madrid", "реал", "мадрид"))
    )


def is_arbeloa_fulham_text(text: str) -> bool:
    return (
        contains_any(text, ("arbeloa", "арбелоа"))
        and contains_any(text, ("fulham", "фулхэм", "фулхема"))
        and contains_any(text, ("coach", "manager", "entrenador", "successor", "predecesor", "тренер", "преемник", "назнач"))
    )


def is_fran_garcia_betis_text(text: str) -> bool:
    if not contains_any(text, ("fran garcia", "fran garcía", "фран гарсия")):
        return False
    if contains_any(text, ("betis", "бетис")) and contains_any(
        text,
        ("transfer", "traspaso", "marcha", "joins", "sign", "fich", "переш", "переход", "трансфер", "подтверд"),
    ):
        return True
    return contains_any(
        text,
        (
            "despedido",
            "despedida",
            "vestuario",
            "salida",
            "se marcha",
            "marcha",
            "traspaso",
            "venta",
            "ganaria",
            "ganaría",
            "conoce que ganaria",
            "conoce que ganaría",
            "earn",
            "would earn",
            "left",
            "leaves",
            "goodbye",
            "farewell",
            "покинул",
            "переход",
            "переш",
            "попрощ",
            "заработ",
        ),
    )


def is_intercontinental_u20_text(text: str) -> bool:
    return (
        contains_any(text, ("intercontinental", "интерконтинент"))
        and contains_any(text, ("u20", "sub 20", "under 20", "до 20", "юнош"))
        and contains_any(text, ("bernabeu", "бернабеу", "santiago wanderers", "сантьяго уондерерс", "final", "финал"))
    )


def is_bastoni_deadline_text(text: str) -> bool:
    return contains_any(text, ("bastoni", "бастони")) and contains_any(
        text,
        ("deadline", "fecha limite", "fecha límite", "bloqueo", "limite", "límite", "дедлайн", "крайний срок", "блок"),
    )


def is_midfield_duo_premier_interest_text(text: str) -> bool:
    has_camavinga = contains_any(text, ("camavinga", "камавинг"))
    has_tchouameni = contains_any(text, ("tchouameni", "tchouameni", "тчуамени"))
    has_duo = contains_any(text, ("midfield duo", "duo", "dueto", "дуэт", "дуо"))
    return (
        ((has_camavinga and has_tchouameni) or has_duo)
        and contains_any(text, ("premier", "manchester united", "united", "манчестер", "премьер"))
        and contains_any(text, ("interest", "target", "offer", "sale", "transfer", "interes", "oferta", "интерес", "предлож", "продаж", "трансфер"))
    )


def is_mourinho_valdebebas_start_text(text: str) -> bool:
    return (
        contains_any(text, ("mourinho", "моуринью"))
        and contains_any(text, ("valdebebas", "вальдебебас"))
        and contains_any(
            text,
            (
                "take charge",
                "takes charge",
                "start work",
                "starts work",
                "first day",
                "puesto a trabajar",
                "trabajar",
                "new real madrid staff",
                "nuevo cuerpo tecnico",
                "nuevo staff",
                "приступил к работе",
                "приступили к работе",
                "начал работу",
                "штаб",
            ),
        )
    )


def is_courtois_world_cup_injury_text(text: str) -> bool:
    return (
        contains_any(text, ("courtois", "куртуа"))
        and contains_any(text, ("injury", "injured", "lesion", "lesion", "травм", "заменен", "заменён", "forced off"))
        and contains_any(text, ("belgium", "belgica", "belgique", "бельг", "spain", "espana", "españa", "испания"))
    )


def is_thiago_pitarch_injury_text(text: str) -> bool:
    """Unify reports about Thiago Pitarch's pre-season knee injury."""
    named_injury = (
        contains_any(text, ("thiago pitarch", "тиаго питарч", "тьяго питарч"))
        and contains_any(
            text,
            ("injury", "injured", "knee", "lesion", "lesionado", "травм", "колен", "выбыл"),
        )
    )
    # One source omitted Pitarch's name but retained the unique two-month detail.
    unnamed_variant = (
        contains_any(
            text,
            (
                "real madrid dealt major injury blow with this youngster",
                "major injury blow with this youngster",
                "серьезный удар из-за травмы молодого игрока",
                "серьёзный удар из-за травмы молодого игрока",
            ),
        )
        and contains_any(text, ("two months", "dos meses", "два месяца"))
    )
    return named_injury or unnamed_variant


def is_bernabeu_summer_works_text(text: str) -> bool:
    return (
        contains_any(text, ("santiago bernabeu", "bernabeu", "бернабеу"))
        and contains_any(
            text,
            (
                "summer glow up",
                "summer update",
                "summer renovation",
                "summer renovations",
                "stadium works",
                "obras en",
                "obras del",
                "obras santiago",
                "renovation",
                "renovations",
                "remodelacion",
                "remodelación",
                "modernization",
            ),
        )
    )


def is_mendy_return_schedule_text(text: str) -> bool:
    """Unify the late-July reports describing Ferland Mendy's recovery timeline."""
    generic_timeline = (
        contains_any(text, ("injured real madrid defender", "defensor lesionado real madrid"))
        and contains_any(text, ("september", "septiembre"))
        and contains_any(text, ("october", "octubre"))
    )
    mendy_training_update = (
        contains_any(text, ("mendy", "ферлан менди", "менди"))
        and contains_any(text, ("cesped", "grass", "training pitch", "entrena"))
        and contains_any(text, ("plazos", "schedule", "return", "vuelve", "regresa"))
    )
    return generic_timeline or mendy_training_update


def is_cucurella_welcome_text(text: str) -> bool:
    """Collapse the post-World-Cup Rodrygo/Cucurella social exchange into one story."""
    return (
        contains_any(text, ("cucurella", "кукурелья"))
        and contains_any(
            text,
            (
                "welcome",
                "welcomes",
                "bienvenida",
                "felicita",
                "congratulat",
                "waiting for you",
                "приветствует",
                "поприветствовал",
                "поздравил",
            ),
        )
        and contains_any(text, ("real madrid", "madrid", "rodrygo", "родриго", "реал"))
    )


def is_cucurella_chelsea_farewell_text(text: str) -> bool:
    """Group repeated reports about Cucurella's farewell to Chelsea."""
    return (
        contains_any(text, ("cucurella", "кукурелья"))
        and contains_any(text, ("chelsea", "челси"))
        and contains_any(
            text,
            ("farewell", "bids farewell", "despedida", "despide", "прощается", "прощание"),
        )
    )


def is_mourinho_documentary_text(text: str) -> bool:
    """Keep trailers and write-ups about the same Mourinho documentary together."""
    return (
        contains_any(text, ("mourinho", "моуринью"))
        and contains_any(text, ("documentary", "documental", "docuseries", "netflix", "трейлер", "документал"))
    )


def is_llopis_goalkeeping_staff_text(text: str) -> bool:
    """Unify reports about the possible Llopis departure from the goalkeeper staff."""
    named_report = (
        contains_any(text, ("luis llopis", "льопис"))
        and contains_any(text, ("leave", "leaving", "departure", "salir", "salida", "покин", "уйти"))
    )
    unnamed_variant = (
        contains_any(text, ("mourinho", "моуринью"))
        and contains_any(text, ("goalkeeping", "goalkeeper", "porteria", "portería", "вратар"))
        and contains_any(text, ("fundamental pillar", "pilar fundamental", "меняет основу", "меняет фундамент"))
    )
    return named_report or unnamed_variant


def is_rodri_real_interest_text(text: str) -> bool:
    """Unify the current Rodri-to-Real-Madrid transfer thread across sources."""
    return (
        contains_any(text, ("rodri", "родри"))
        and contains_any(text, ("real madrid", "real", "madrid", "реал"))
        and contains_any(
            text,
            (
                "interest",
                "interes",
                "fichar",
                "fichaje",
                "sign",
                "signing",
                "best players",
                "mejores jugadores",
                "хочет подписать",
                "интересуется",
            ),
        )
    )


def is_valverde_mourinho_leadership_text(text: str) -> bool:
    """Keep the first-day Valverde/Mourinho leadership quotes in one story."""
    return (
        contains_any(text, ("valverde", "вальверде"))
        and contains_any(text, ("mourinho", "моуринью"))
        and contains_any(
            text,
            (
                "captain",
                "captaincy",
                "learn",
                "learning",
                "aprend",
                "rendido",
                "hails",
                "first day",
                "primer dia",
                "учиться",
                "капитан",
                "повязк",
            ),
        )
    )


def is_real_madrid_green_away_kit_text(text: str) -> bool:
    """Group the July 2026 green away-kit stories across all source wording."""
    return (
        contains_any(text, ("real madrid", "реал мадрид", "madrid", "мадрид"))
        and contains_any(text, ("green", "verde", "зелён", "зелен"))
        and contains_any(
            text,
            (
                "away kit",
                "away shirt",
                "second kit",
                "second shirt",
                "segunda equipacion",
                "segunda camiseta",
                "equipacion",
                "equipación",
                "camiseta",
                "гостев",
                "вторая форма",
            ),
        )
    )


def is_yan_diomande_real_transfer_text(text: str) -> bool:
    """Collapse the current Yan Diomande transfer saga across all source phrasings."""
    return contains_any(text, ("yan diomande", "ян диоманде", "diomande", "диоманде"))


def is_carlos_espi_real_transfer_text(text: str) -> bool:
    """Collapse the Carlos Espi signing and immediate follow-up coverage."""
    return contains_any(
        text,
        (
            "carlos espi",
            "карлос эспи",
            "primeras palabras de espi",
            "primeras palabras espi",
            "espi madridista",
            "espi first words",
        ),
    )


def is_victor_valdepenas_fiorentina_text(text: str) -> bool:
    """Collapse confirmation stories for Victor Valdepenas's Fiorentina move."""
    return (
        contains_any(text, ("victor valdepenas", "виктор вальдепеньяс", "виктор вальдепес"))
        and contains_any(text, ("fiorentina", "фиорентина"))
    )


def semantic_news_key(title: str, summary: str = "") -> str:
    text = normalize_news_text(f"{title} {summary}")

    if is_bernabeu_summer_works_text(text):
        return "club:bernabeu-summer-works"

    if is_courtois_world_cup_injury_text(text):
        return "injury:courtois-belgium-world-cup"

    if is_thiago_pitarch_injury_text(text):
        return "injury:thiago-pitarch-knee"

    if is_raul_asencio_preseason_injury_text(text):
        return "injury:raul-asencio-preseason-muscle"

    if is_llopis_goalkeeping_staff_text(text):
        return "staff:llopis-goalkeeping"

    if is_mendy_return_schedule_text(text):
        return "injury:mendy-return-schedule"

    if is_cucurella_welcome_text(text):
        return "social:rodrygo-cucurella-world-cup-welcome"

    if is_cucurella_chelsea_farewell_text(text):
        return "transfer:cucurella-chelsea-farewell"

    if is_mourinho_documentary_text(text):
        return "media:mourinho-documentary"

    if is_real_madrid_green_away_kit_text(text):
        return "club:green-away-kit-2026-27"

    if is_yan_diomande_real_transfer_text(text):
        return "transfer:yan-diomande-real-madrid"

    if is_carlos_espi_real_transfer_text(text):
        return "transfer:carlos-espi-real-madrid"

    if is_victor_valdepenas_fiorentina_text(text):
        return "transfer:victor-valdepenas-fiorentina"

    if is_rodri_real_interest_text(text):
        return "transfer:rumour:rodri"

    if is_valverde_mourinho_leadership_text(text):
        return "club:valverde-mourinho-leadership"

    if is_laliga_opener_postponed_text(text):
        return "schedule:laliga-opener-postponed"

    if is_teresa_herrera_deportivo_text(text):
        return "schedule:teresa-herrera-deportivo-friendly"

    if is_fiorentina_austria_friendly_text(text):
        return "schedule:preseason-fiorentina-austria-friendly"

    if is_schalke_preseason_friendly_text(text):
        return "schedule:preseason-schalke-04-friendly"

    if is_mastantuono_river_loan_text(text):
        return "transfer:loan:mastantuono-river-plate"

    if is_mastantuono_roma_transfer_text(text):
        return "transfer:loan:mastantuono-roma"

    if is_fulham_palacios_garcia_text(text):
        return "transfer:fulham-palacios-garcia"

    if is_gonzalo_fulham_transfer_text(text):
        return "transfer:gonzalo-fulham"

    if is_arbeloa_fulham_text(text):
        return "staff:arbeloa-fulham-manager"

    if is_mourinho_valdebebas_start_text(text):
        return "staff:mourinho-starts-at-valdebebas"

    if is_fran_garcia_betis_text(text):
        return "transfer:fran-garcia-betis"

    if is_haaland_family_real_text(text):
        return "transfer:haaland-family-real-links"

    if is_intercontinental_u20_text(text):
        return "academy:u20-intercontinental-cup-final"

    if is_bastoni_deadline_text(text):
        return "transfer:bastoni-deadline"

    if is_midfield_duo_premier_interest_text(text):
        return "transfer:midfield-duo-premier-interest"

    if is_tchouameni_extension_text(text):
        return "contract:tchouameni-extension"

    if is_vinicius_renewal_text(text):
        return "contract:vinicius-renewal"

    if is_player_sales_revenue_text(text):
        return "finance:player-sales-revenue"

    if is_valverde_stays_real_text(text):
        return "player:valverde-stays-real-madrid"

    if is_modric_career_decision_noise_text(text):
        return "noise:modric-career-decision-after-world-cup"

    if is_enzo_denial_text(text):
        return "transfer:no-sign:enzo-fernandez"

    if is_camavinga_manchester_city_text(text):
        return "transfer:camavinga-manchester-city"

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

    if is_laliga_harassment_protocol_text(text):
        return "legal:laliga-harassment-protocol"

    if is_olise_bayern_talks_text(text):
        return "transfer:olise-bayern-talks-real-monitoring"

    if is_asencio_loan_buy_text(text):
        return "transfer:loan:asencio-mandatory-buy"

    if is_medical_staff_changes_text(text):
        return "staff:medical-overhaul-after-injuries"

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
    if is_bernabeu_summer_works_text(text):
        return "club:bernabeu-summer-works"
    if is_mendy_return_schedule_text(text):
        return "injury:mendy-return-schedule"
    if is_thiago_pitarch_injury_text(text):
        return "injury:thiago-pitarch-knee"
    if is_raul_asencio_preseason_injury_text(text):
        return "injury:raul-asencio-preseason-muscle"
    if is_llopis_goalkeeping_staff_text(text):
        return "staff:llopis-goalkeeping"
    if is_cucurella_welcome_text(text):
        return "social:rodrygo-cucurella-world-cup-welcome"
    if is_cucurella_chelsea_farewell_text(text):
        return "transfer:cucurella-chelsea-farewell"
    if is_mourinho_documentary_text(text):
        return "media:mourinho-documentary"
    if is_real_madrid_green_away_kit_text(text):
        return "club:green-away-kit-2026-27"
    if is_yan_diomande_real_transfer_text(text):
        return "transfer:yan-diomande-real-madrid"
    if is_carlos_espi_real_transfer_text(text):
        return "transfer:carlos-espi-real-madrid"

    if is_victor_valdepenas_fiorentina_text(text):
        return "transfer:victor-valdepenas-fiorentina"
    if is_rodri_real_interest_text(text):
        return "transfer:rumour:rodri"
    if is_valverde_mourinho_leadership_text(text):
        return "club:valverde-mourinho-leadership"
    if is_venezuela_donation_text(text):
        return "club:donation:venezuela-earthquake"
    if is_joan_martinez_valencia_text(text):
        return "transfer:loan:joan-martinez-valencia"
    if is_laliga_rfef_meeting_text(text):
        return "club:laliga-rfef-meeting-skip"
    if is_laliga_harassment_protocol_text(text):
        return "legal:laliga-harassment-protocol"
    if is_camavinga_manchester_city_text(text):
        return "transfer:camavinga-manchester-city"
    if is_laliga_opener_postponed_text(text):
        return "schedule:laliga-opener-postponed"
    if is_teresa_herrera_deportivo_text(text):
        return "schedule:teresa-herrera-deportivo-friendly"
    if is_fiorentina_austria_friendly_text(text):
        return "schedule:preseason-fiorentina-austria-friendly"
    if is_schalke_preseason_friendly_text(text):
        return "schedule:preseason-schalke-04-friendly"
    if is_mastantuono_river_loan_text(text):
        return "transfer:loan:mastantuono-river-plate"

    if is_mastantuono_roma_transfer_text(text):
        return "transfer:loan:mastantuono-roma"
    if is_fulham_palacios_garcia_text(text):
        return "transfer:fulham-palacios-garcia"
    if is_gonzalo_fulham_transfer_text(text):
        return "transfer:gonzalo-fulham"
    if is_arbeloa_fulham_text(text):
        return "staff:arbeloa-fulham-manager"
    if is_fran_garcia_betis_text(text):
        return "transfer:fran-garcia-betis"
    if is_haaland_family_real_text(text):
        return "transfer:haaland-family-real-links"
    if is_intercontinental_u20_text(text):
        return "academy:u20-intercontinental-cup-final"
    if is_bastoni_deadline_text(text):
        return "transfer:bastoni-deadline"
    if is_midfield_duo_premier_interest_text(text):
        return "transfer:midfield-duo-premier-interest"
    if is_tchouameni_extension_text(text):
        return "contract:tchouameni-extension"
    if is_vinicius_renewal_text(text):
        return "contract:vinicius-renewal"
    if is_player_sales_revenue_text(text):
        return "finance:player-sales-revenue"
    if is_valverde_stays_real_text(text):
        return "player:valverde-stays-real-madrid"
    if is_modric_career_decision_noise_text(text):
        return "noise:modric-career-decision-after-world-cup"
    if is_enzo_denial_text(text):
        return "transfer:no-sign:enzo-fernandez"
    if is_olise_bayern_talks_text(text):
        return "transfer:olise-bayern-talks-real-monitoring"
    if is_asencio_loan_buy_text(text):
        return "transfer:loan:asencio-mandatory-buy"
    if is_nico_paz_como_text(text):
        return "transfer:nico-paz-como"
    if is_medical_staff_changes_text(text):
        return "staff:medical-overhaul-after-injuries"
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
