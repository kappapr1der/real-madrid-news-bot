#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import escape
from zoneinfo import ZoneInfo

import requests

from sources_international import SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU
from filters import is_handle_only_x_title, passes_filters
from feed_utils import is_repost_entry, parse_feed_url, source_is_x
from match_calendar import digest_block_reason
from news_fingerprint import load_news_keys, save_news_keys, semantic_news_key, ucl_draw_event_key
from post_utils import append_hashtags
from publication_registry import published_editorial_links
from content_quality import RankedDigestItem, candidate_profile, rank_digest_candidates
from editorial_archive import archive_digest_items
from llm_editor import review_digest_items
from source_quality import source_provenance_label, update_digest_source_quality
from status_manager import record_error, record_status
from translator import translate_text
from text_cleaner import clean_text
from visual_cards import render_news_card
from runtime_config import (
    DIGEST_DAY_LOOKBACK_HOURS,
    DIGEST_DEDUPE_ENABLED,
    DIGEST_DEDUPE_SIMILARITY,
    DIGEST_DEFAULT_LOOKBACK_HOURS,
    DIGEST_ENTRY_SCAN_LIMIT,
    DIGEST_EVENING_LOOKBACK_HOURS,
    DIGEST_HASHTAGS,
    DIGEST_INCLUDE_UNDATED,
    DIGEST_LIMIT,
    DIGEST_MIN_ITEMS_TO_POST,
    DIGEST_MORNING_LOOKBACK_HOURS,
    DIGEST_NIGHT_LOOKBACK_HOURS,
    DIGEST_PRIORITY_SORT_ENABLED,
    DIGEST_SHORT_FORMAT_THRESHOLD,
    DIGEST_SHOW_RELATED_SOURCES,
    DIGEST_TIMEZONE,
    DRY_RUN,
    LLM_EDITOR_MAX_DIGEST_ITEMS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_MESSAGE_LIMIT,
    TELEGRAM_TIMEOUT_SECONDS,
    TARGET_CHAT_ID,
    UCL_DRAW_DATE,
    get_log_file,
    get_state_file,
    telegram_configured,
)

LOG_FILE = get_log_file("digest.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

SENT_FILE = get_state_file("sent_links.txt")
SENT_BREAKING_FILE = get_state_file("sent_breaking.txt")
SENT_BREAKING_FINGERPRINT_FILE = get_state_file("sent_breaking_fingerprints.txt")
QUARANTINE_FILE = get_state_file("digest_quarantine.json")
TEMPLATE_HISTORY_FILE = get_state_file("digest_template_history.json")
QUARANTINE_LIMIT = 200
TEMPLATE_HISTORY_LIMIT = 4
TZ = ZoneInfo(DIGEST_TIMEZONE)

DIGEST_LLM_HARD_DENY_TERMS = (
    "francia gana",
    "france wins",
    "world cup",
    "2026 world cup",
    "world cup spotlight",
    "madrid world cup spotlight",
    "mundial",
    "чемпионат мира",
    "чемпионата мира",
    "сборная",
    "сборной",
    "сборную",
    "national team",
    "франция выигрывает",
    "франция выиграла",
    "hat-trick ousmane",
    "ousmane dembele",
    "усман дембеле",
    "дембеле",
    "mbappe solidario",
    "mbappé solidario",
    "solidario mejor mundial",
    "mejor del mundial",
    "мбаппе стал третьим",
    "самый поддерживающий мбаппе",
    "мбаппе уже стал лучшим",
    "лучшим в мире",
    "20+ результатив",
    "haaland",
    "хааланд",
    "эрлинг хааланд",
    "a bernardo silva no le sienta bien el mundial",
    "bernardo silva desaparece mapa",
    "бернарду сильве не нравится чемпионат мира",
    "jhon cordoba",
    "john cordoba",
    "джон кордоба",
    "джона кордобы",
    "подробности по травме джона кордобы",
    "шансах сыграть на чм",
    "fede valverde accepts responsibility",
    "accepts responsibility after uruguay",
    "uruguay's world cup exit",
    "uruguays world cup exit",
    "wasn't up to it",
    "wasn t up to it",
    "i know i wasn",
    "i know i was not",
    "феде вальверде берет на себя ответственность",
    "феде вальверде берёт на себя ответственность",
    "после вылета сборной уругвая",
    "я знаю, что был не готов",
    "bonito reencuentro cristiano ronaldo rodrygo",
    "cristiano ronaldo rodrygo portugues preocupo lesion",
    "cristiano ronaldo delivers a clear message",
    "clear message to the football world",
    "message to the football world",
    "cristiano ronaldo y rodrygo",
    "reencuentro cristiano rodrygo",
    "reencuentro cristiano-rodrygo",
    "cristiano-rodrygo",
    "криштиану роналду и родриго",
    "возвращение криштиану и родриго",
    "португалец беспокоился о своей травме",
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
    "ronaldo nazario",
    "ronaldo nazário",
    "ronaldo-nazario-mbappe",
    "ronaldo-nazario-mbappe-me-recuerda",
    "mbappe recuerda mi prime",
    "mbappé recuerda mi prime",
    "mbappe me recuerda",
    "mbappé me recuerda",
    "мбаппе напоминает мне меня",
    "роналду назарио: мбаппе",
    "роналду забыл о винисиусе",
    "забыл о винисиусе",
    "я не вижу другого такого, как неймар",
    "другого такого, как неймар",
    "me encanta venir",
    "estas vistas",
    "cuando marco gol",
    "виды",
    "забиваю гол",
    "bielsa",
    "бьелса",
    "valverde y estrellas uruguay",
    "вальверде и звезды уругвая",
    "carlo ancelotti refuses engage japan mind games",
    "brazil manager carlo ancelotti refuses",
    "brazil-manager-carlo-ancelotti",
    "carlo ancelotti has turned brazil",
    "brazil carlo ancelotti world cup",
    "turned brazil into potential world cup winner",
    "potential world cup winner",
    "japan mind games",
    "japan-mind-games",
    "round 32 clash world cup",
    "японских интеллектуальных играх",
    "анчелотти отказывается участвовать",
    "интеллектуальных играх",
    "как формируется новая бразилия",
    "new brazil taking shape",
    "new brazil is taking shape",
    "how new brazil is taking shape",
    "cunha plays key role",
    "кунья играет ключевую роль",
    "fede valverde's uruguay eliminated",
    "valverde's uruguay",
    "uruguay eliminated",
    "сборная уругвая",
    "вылетела с чемпионата мира",
    "spain clinch first place",
    "marc cucurella features",
    "win over uruguay",
    "cucurella vuela en el mundial",
    "madrid se frotan las manos",
    "real madrid protagonista en la tanda de penaltis",
    "tanda de penaltis del australia",
    "australia-egipto",
    "australia egipto",
    "bellingham 23 anos sobre lo que mas le gusta de espana",
    "para caminar por una gran ciudad",
    "bellingham became tuchel",
    "bellingham has become tuchel",
    "tuchel's most important player",
    "tuchel most important player",
    "most important player for tuchel",
    "important player tuchel",
    "беллингем стал важнейшим игроком тухеля",
    "важнейшим игроком тухеля",
    "what thomas tuchel did to trent",
    "tuchel did to trent",
    "trent alexander-arnold feels like a fireable offense",
    "fireable offense",
    "тухель сделал с трентом",
    "преступление, за которое можно уволить",
    "real madrid players still going strong at the world cup",
    "players still going strong at the world cup",
    "world cup for the round of 32",
    "round of 32",
    "по-прежнему сильны на чемпионате мира",
    "игроков мадридского \"реала\" по-прежнему сильны",
    "испания завоевала первое место",
    "голу марка кукуреллы",
    "победу над уругваем",
    "courtois belgica",
    "courtois belgium",
    "belgica siguen adelante",
    "france vs norway",
    "france against norway",
    "francia contra noruega",
    "francia noruega",
    "flipped the narrative",
    "during france vs norway",
    "куртуа и бельгия",
    "бельгия продолжа",
    "первое место в группе",
    "center of controversy",
    "centre of controversy",
    "controversy again",
    "controversia",
    "polémica",
    "polemica",
    "снова в центре скандала",
    "juancho hernangomez",
    "juancho hernangómez",
    "хуанчо эрнангомес",
    "baloncesto",
    "баскетбол",
    "entra historia belgica",
    "historia belgica",
    "historia de belgica",
    "belgium history",
    "history of belgium",
    "agustin canobbio",
    "canobbio",
    "apellido verdugo real madrid",
    "expulsion contra espana",
    "channing tatum",
    "actor channing",
    "actor chenning",
    "norway and france",
    "noruega y francia",
    "uruguay vuelve firmar",
    "dolorosa eliminacion fase grupos",
    "dolorosa eliminacion",
    "fase de grupos",
    "bernardo silva stays on the bench",
    "portugal's 0-0 draw with colombia",
    "portugals 0-0 draw with colombia",
    "portugal 0-0 draw with colombia",
    "portugal colombia",
    "rodrygo appears in miami",
    "rodrygo aparece en miami",
    "saca primera foto de equipo",
    "saca la primera foto de equipo",
    "primera foto equipo",
    "first team photo with bernardo",
    "first photo with summer signing",
    "shares first photo with summer signing",
    "image real madrid winger shares first photo",
    "real madrid winger shares first photo",
    "bienvenida rodrygo bernardo silva",
    "bienvenida rodrygo",
    "welcomes bernardo silva",
    "bienvenida de rodrygo",
    "la bienvenida de rodrygo",
    "bienvenida a bernardo silva",
    "rodrygo a bernardo silva",
    "familia cule cucurella",
    "familia culé cucurella",
    "familia cule de cucurella",
    "familia culé de cucurella",
    "семья куле кукурельи",
    "dani carvajal 34 anos sobre futbol",
    "jovenes deben disfrutar deporte",
    "redes sociales ya quieren ser futbolistas",
    "young people should enjoy sport",
    "micah richards told it like it is",
    "trent alexander-arnold controversy",
    "addressing trent alexander-arnold controversy",
    "toni kroos said what liverpool and bayern",
    "fans are terrified to confess",
    "gary neville affirmed",
    "real madrid fans have been saying for weeks",
    "fans have been saying for weeks about trent",
    "gary neville exfutbolista",
    "tuchel no ha querido en mundial",
    "alexander-arnold es clase mundial",
    "alexander arnold es clase mundial",
    "laterales propensos lesionarse",
    "giro mundial brahim",
    "lider con marruecos",
    "líder con marruecos",
    "lГ­der con marruecos",
    "marruecos real madrid mourinho",
    "leader with morocco",
    "messi mbappe",
    "messi, mbappe",
    "vozinha",
    "opta",
    "СЃРёРјРІРѕР»РёС‡РµСЃРєРѕР№ СЃР±РѕСЂРЅРѕР№ РіСЂСѓРїРїРѕРІРѕРіРѕ СЌС‚Р°РїР°",
    "СЃР±РѕСЂРЅРѕР№ РіСЂСѓРїРїРѕРІРѕРіРѕ СЌС‚Р°РїР° С‡Рј",
    "rincon madrid en bellingham",
    "rincón madrid en bellingham",
    "rincГіn madrid en bellingham",
    "bellingham tiene dos casas",
    "antiguo coto caza",
    "zonas verdes",
    "10 minutos santiago bernabeu",
    "СѓРіРѕР»РѕРє РјР°РґСЂРёРґР°",
    "Р±РµР»Р»РёРЅРіРµРјР° РµСЃС‚СЊ РґРІР° РґРѕРјР°",
    "РѕС…РѕС‚РЅРёС‡СЊРµ СѓРіРѕРґСЊРµ",
    "Р·РµР»РµРЅС‹Рµ РЅР°СЃР°Р¶РґРµРЅРёСЏ",
    "laporta contra cuerdas",
    "barcelona debe este ano",
    "barcelona debe este año",
    "barcelona debe este aГ±o",
    "goldman sachs",
    "camp nou",
    "Р»Р°РїРѕСЂС‚Р°",
    "РіРѕР»РґРјР°РЅ СЃР°РєСЃ",
    "antonio rudiger 33 anos futbolista real madrid infancia pobreza",
    "antonio rüdiger 33 anos futbolista real madrid infancia pobreza",
    "infancia pobreza",
    "infancia estuvo marcada",
    "pobreza",
    "si habia pollo en la mesa",
    "si había pollo en la mesa",
    "если на столе была курица",
    "детство было отмечено бедностью",
)

DIGEST_LLM_ABSOLUTE_DENY_TERMS = (
    "chelsea poised to sign morgan rogers",
    "morgan rogers from aston villa",
    "new season campaign",
    "become an official real madrid fan",
    "campana nueva temporada",
    "hazte aficionado oficial real madrid",
    "empieza la nueva temporada como fan oficial",
    "how old will every real madrid player be at the 2030 world cup",
    "edad tendran todos jugadores real madrid proximo mundial 2030",
    "la edad que tendrán todos los jugadores del real madrid en el próximo mundial 2030",
    "fc27",
    "portada fc27",
    "enzo fernandez says argentina played with pride and humility",
    "morgan rogers",
    "sensible changes",
    "vinicius 26 sobre su familia",
    "vivi con mi abuela nilza",
    "grandmother nilza",
    "problema real madrid sigue sin resolver",
    "the problem real madrid have still not solved",
    "ea fc 27",
    "ea fc27",
    "real madrid misses out on the chance to sign one of europes best defenders",
    "real madrid miss out on the chance to sign one of europe's best defenders",
    "alba redondo deja real madrid",
    "alba redondo leaves real madrid",
    "doris dipetta",
    "madre de fede valverde",
    "three real madrid players included in the 2026 fifa world cup best xi",
    "mundial dispara real madrid",
    "mundial dispara al real madrid",
    "expertos en climatizacion",
    "expertos en climatización",
    "air conditioning remote",
    "real madrid trio see market values soar after impressive world cup displays",
    "every real madrid fan has been asking for",
    "afa statement on president's detention",
    "afa statement on the president's detention",
    "torres ready to leave barcelona",
    "заявление afa о задержании президента",
    "торрес готов покинуть барселону",
    "raul arevalo",
    "raul arévalo",
    "real madrid land 3 stars in fifa's official best xi",
    "modric renueva con milan",
    "modric renueva con el milan",
    "modric renews with milan",
    "calendario pretemporada 2026/27: fechas, horarios y donde ver todos los amistosos",
    "calendario de pretemporada 2026/27: fechas, horarios y donde ver todos los amistosos",
    "desvelan intrahistoria fichaje pedrerol chiringuito mediaset",
    "intrahistoria del fichaje de pedrerol",
    "one of the bright spots of real madrid's season ready to take another leap",
    "psg dispuesto a romper definitivamente el fichaje de enzo por el real madrid",
    "would not accept transfer: insider floats possibility of karim benzema",
    "glavnyj trener rodiny oharakterizoval novichka",
    "главный тренер родины охарактеризовал новичка",
    "expertos en cirugia plastica coinciden",
    "expertos en cirugía plástica coinciden",
    "compra tus entradas betis vs real madrid",
    "sergio llull",
    "серхио люлль",
    "maria trisac",
    "мария трисак",
    "vinicius da la cara y presume de nueva imagen",
    "винисиус поворачивается лицом и хвастается",
    "zidane set to be announced as mbappe and tchouameni",
    "reflexion iker casillas 45 anos",
    "reflexión iker casillas 45 años",
    "courtois ensena espectacular porsche gt3",
    "courtois muestra su porsche gt3",
    "courtois o de bruyne",
    "courtois o de bruyne quien vale mas",
    "кто из бывших друзей и легенд сборной бельгии стоит дороже",
    "real sociedad con zakharyan se impone al wolves",
    "реал сосьедад с захаряном одержал победу над вулверхэмптоном",
    "i prefer not to speak",
    "я предпочитаю молчать 26 июля 2026",
    "balon de oro marca las normas",
    "balón de oro marca las normas",
    "mbappe se coloca como principal candidato",
    "mbappé se coloca como principal candidato",
    "the last time in budapest",
    "реал возвращается в будапешт",
    "craig overton",
    "battle with brother jamie",
    "dramatic hundred finish",
    "welbeck",
    "уэлбек",
    "carta abierta mbappe",
    "carta abierta mbappé",
    "carta abierta de mbappe",
    "carta abierta de mbappé",
    "open letter mbappe",
    "открытое письмо мбаппе",
    "endrick 20 anos cuando era nino",
    "endrick 20 años cuando era niño",
    "mi madre solia llevarse biblia",
    "mi madre solía llevarse biblia",
    "no teniamos tv ni internet en casa",
    "no teníamos tv ni internet en casa",
    "у нас дома не было телевизора или интернета",
    "real madrid are finally realising their biggest mistake",
    "finally realising their biggest mistake of this transfer window",
    "kylian mbappe 27 anos no voy a ser entrenador",
    "kylian mbappé 27 años no voy a ser entrenador",
    "no voy a ser entrenador despues de mi carrera",
    "no voy a ser entrenador después de mi carrera",
    "zinedine zidane confirmed as france manager",
    "zidane confirmed as new france manager",
    "chelsea unveil trialist in first game under xabi alonso",
    "first game under xabi alonso",
    "aritz gabilondo",
    "aritz gabilondo comunicador sobre llegada mastantuono real sociedad",
    "real madrid baraja nombres heredero thibaut courtois",
    "heredero thibaut courtois",
    "madrid se mete en un problema",
    "real madrid faces the need for operations in the transfer market",
    "argentina make 3 changes to lineup",
    "argentina makes 3 changes to lineup",
    "argentina 3 changes to lineup",
    "argentina 3 changes lineup",
    "espana domina al descanso",
    "spain dominate at half time",
    "spain dominates at half time",
    "a 120 million decision could haunt real madrid",
    "120 million decision could haunt",
    "vinicius estrena nuevo look",
    "vinicius unveils new look",
    "vinicius new look",
    "asencio se resiste a salir",
    "bloquearia llegada de bastoni",
    "cucurella quiere asaltar el olimpo",
    "zidane ya tiene fecha para ser seleccionador",
    "jude bellingham is england's next captain",
    "partido de sus vidas",
    "prensa pide segunda estrella",
    "alba redondo cerca de fichar por la juventus",
    "tomas guasch",
    "tomás guasch",
    "томас гуаш",
    "fichar olise es capricho",
    "spain and marc cucurella crowned world cup champions",
    "cucurella crowned world cup champions",
    "rodri rodri rodri",
    "rodri, rodri, rodri",
    "toni kroos heroico triunfo espana",
    "toni kroos y el heroico triunfo",
    "heroic spain triumph kroos",
    "real madrid fichado lateral izquierdo mundo",
    "real madrid has signed the best left back in the world",
    "real madrid defender determined to stay",
    "potentially blocking alessandro bastoni move",
    "mantienen el bloqueo al fichaje de yan diomande por el psg",
    "bloqueo al fichaje de yan diomande por el psg",
    "mantienen-bloqueo-fichaje-yan-diomande-psg",
    "once ideal del mundial",
    "ideal world cup xi",
    "real madrid have doubts over the suitability of superstar trio",
    "doubts over the suitability of superstar trio",
    "letras gigantes acero inoxidable fachada bernabeu",
    "aparece incognita sobre letras gigantes acero inoxidable",
    "iris ashley deja real madrid",
    "iris ashley deja el real madrid",
    "real madrid consider move for bayern munich superstar unfeasible",
    "quillo barrios comunicador",
    "argentina tiene grandeza madrid",
    "courtois presentara plataforma inversion madrid",
    "mendy entrena cesped lunin gimnasio",
    "mendy entrena cesped, lunin gimnasio",
    "novedades mercado afirman interes ferran torres",
    "novedades mercado: afirman interes ferran torres",
    "vinicius luce nueva imagen",
    "carlo ancelotti was right about wanting this spanish midfielder at real madrid in 2022",
    "verstappen",
    "red bull",
    "ферстаппен",
    "ред булл",
    "casillas sobre relacion con mourinho",
    "casillas sobre su relacion con mourinho",
    "casillas mourinho fue un matrimonio",
    "casillas - mourinho marriage",
    "casillas mourinho relationship",
    "касильяс об отношениях с моуринью",
    "это был брак который плохо закончился",
    "kasilyas-ob-otnosheniyah-s-mourinyu",
    "eto-byl-brak-kotoryj-ploho-zakonchilsya",
    "real madrid activa plan renovacion firma estrellas",
    "real madrid activa el plan renovacion firma estrellas",
    "activa plan renovacion firma estrellas",
    "activa el plan renovacion firma sus estrellas",
    "activa plan renovacion firma sus estrellas",
    "plan renovacion firma sus estrellas",
    "activa el plan renovacion: firma sus estrellas",
    "activa plan renovacion: firma sus estrellas",
    "plan renovacion: firma sus estrellas",
    "real-madrid-activa-plan-renovacion-firma-estrellas",
    "juancho hernangomez",
    "juancho hernangómez",
    "хуанчо эрнангомес",
    "jaime pradilla",
    "pradilla",
    "хайме прадилья",
    "прадилья",
    "baloncesto",
    "баскетбол",
    "agustin canobbio",
    "canobbio",
    "apellido verdugo real madrid",
    "expulsion contra espana",
    "first photo with summer signing",
    "shares first photo with summer signing",
    "bienvenida rodrygo",
    "bienvenida de rodrygo",
    "la bienvenida de rodrygo",
    "welcomes bernardo silva",
    "familia cule cucurella",
    "familia culé cucurella",
    "gary neville affirmed",
    "real madrid fans have been saying for weeks",
    "gary neville exfutbolista",
    "tuchel no ha querido en mundial",
    "man united legends question tuchel",
    "tuchel's decision to omit real madrid superstar",
    "tuchel decision to omit real madrid superstar",
    "omit real madrid superstar",
    "head scratcher",
    "решение тухеля не вызвать",
    "не вызвать суперзвезду реала",
    "no seguirle en instagram",
    "seguirle en instagram",
    "tardo 10 horas en hacerlo",
    "tardó 10 horas en hacerlo",
    "dardo de courtois a cucurella",
    "queja de courtois",
    "courtois a cucurella",
    "instagram",
    "инстаграм",
    "ya no cree en el fichaje de este jugador",
    "no cree en el fichaje de este jugador",
    "больше не верит в трансфер этого игрока",
    "больше не верит в переход этого игрока",
    "трансфер этого игрока",
    "переход этого игрока",
    "manolo lama",
    "lesion raphinha ha venido bien",
    "lesión raphinha ha venido bien",
    "no brasil ahora se siente superestrella",
    "todos van jugar el",
    "todos van a jugar el",
    "hora juegan madridistas mundial",
    "cuando juegan madridistas mundial",
    "madridistas mundial",
    "reranking europe top clubs player performance world cup",
    "top clubs player performance world cup",
    "reranking europe's top clubs",
    "player performance at the world cup",
    "player performance world cup",
    "tuchel's most important player",
    "беллингем стал важнейшим игроком тухеля",
    "a bernardo silva no le sienta bien el mundial",
    "bernardo silva desaparece mapa",
    "бернарду сильве не нравится чемпионат мира",
    "jhon cordoba",
    "john cordoba",
    "джон кордоба",
    "джона кордобы",
    "подробности по травме джона кордобы",
    "шансах сыграть на чм",
    "fede valverde accepts responsibility",
    "accepts responsibility after uruguay",
    "uruguay's world cup exit",
    "uruguays world cup exit",
    "wasn't up to it",
    "wasn t up to it",
    "i know i wasn",
    "i know i was not",
    "феде вальверде берет на себя ответственность",
    "феде вальверде берёт на себя ответственность",
    "после вылета сборной уругвая",
    "я знаю, что был не готов",
    "bonito reencuentro cristiano ronaldo rodrygo",
    "cristiano ronaldo y rodrygo",
    "cristiano ronaldo delivers a clear message",
    "clear message to the football world",
    "message to the football world",
    "cristiano ronaldo went no lies detected",
    "no lies detected on portugal legacy",
    "portugal legacy with uncomfortable truth",
    "reencuentro cristiano-rodrygo",
    "возвращение криштиану и родриго",
    "криштиану роналду рассказал о своем португальском наследии",
    "португальском наследии",
    "ronaldo nazario",
    "ronaldo nazário",
    "ronaldo-nazario-mbappe",
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
    "модрич должен принять решение",
    "карьерное решение после вылета с чемпионата мира",
    "реал в бегах",
    "мбаппе напоминает мне меня",
    "роналду забыл о винисиусе",
    "забыл о винисиусе",
    "japan mind games",
    "japan-mind-games",
    "анчелотти отказывается участвовать",
    "интеллектуальных играх",
    "new brazil taking shape",
    "new brazil is taking shape",
    "how new brazil is taking shape",
    "cunha plays key role",
    "carlo ancelotti has turned brazil",
    "brazil carlo ancelotti world cup",
    "turned brazil into potential world cup winner",
    "potential world cup winner",
    "infancia pobreza",
    "infancia estuvo marcada",
    "pobreza",
    "si habia pollo en la mesa",
    "players still going strong at the world cup",
    "round of 32",
    "paraguay france live",
    "paraguay - france",
    "paraguay-france",
    "france morocco live",
    "france - morocco",
    "france-morocco",
    "france morocco live stream",
    "live stream score result world cup quarter final",
    "olise appeal rejected",
    "appeal michael olise rejected",
    "appeal rejected by fifa",
    "atlas lions",
    "парагвай - франция",
    "прямая трансляция матча парагвай",
    "paraguay no pudo con mbappe",
    "paraguay no pudo con mbappé",
    "paraguay hates mbappe",
    "paraguay odia mbappe",
    "senadora celeste amenaza mbappe",
    "celeste amarilla comments",
    "colonized cameroonian",
    "colonizado camerunes",
    "сенатор селеста угрожает мбаппе",
    "парагвай не сломил мбаппе",
    "парагвай ненавидит мбаппе",
    "скандал между мбаппе и сенатором",
    "cucurella vuela en el mundial",
    "madrid se frotan las manos",
    "marc cucurella reflected every real madrid fan",
    "cucurella reflected every real madrid fan",
    "cucurellas spain knock out portugal",
    "cucurella's spain knock out portugal",
    "марк кукурелла отразил всех болельщиков",
    "сборная испании в составе марка кукуреллы",
    "real madrid protagonista en la tanda de penaltis",
    "tanda de penaltis del australia",
    "australia-egipto",
    "australia egipto",
    "bellingham 23 anos sobre lo que mas le gusta de espana",
    "para caminar por una gran ciudad",
    "alexander-arnold es clase mundial",
    "alexander arnold es clase mundial",
    "laterales propensos lesionarse",
    "does carlo ancelotti hate endrick",
    "carlo ancelotti hate endrick",
    "hate endrick",
    "ненавидит эндрика",
    "так ли это на самом деле",
    "divertido momento marcelo linda caicedo",
    "divertido momento entre marcelo",
    "marcelo linda caicedo",
    "забавный момент между марсело и линдой кайседо",
    "giro mundial brahim",
    "lider con marruecos",
    "messi mbappe",
    "vozinha",
    "opta",
    "rincon madrid en bellingham",
    "bellingham tiene dos casas",
    "antiguo coto caza",
    "zonas verdes",
    "fallece padre ricardo carvalho",
    "padre de ricardo carvalho",
    "ricardo carvalho father",
    "father of ricardo carvalho",
    "скончался отец рикарду карвалью",
    "laporta contra cuerdas",
    "barcelona debe este ano",
    "barcelona debe este año",
    "barcelona debe este aГ±o",
    "goldman sachs",
    "camp nou",
    "4 champions eclipsan",
    "eclipsan eliminatoria seleccion",
    "ni 4 campeones",
    "ни 4 чемпиона",
    "so much for the endrick breakout",
    "endrick breakout under carlo ancelotti",
    "secret laboratory ancelotti",
    "laboratorio secreto ancelotti",
    "transformacion genio",
    "transformación genio",
    "как анчелотти переворачивает матчи чм",
    "секретная лаборатория анчелотти",
    "поиск пути к гекса",
    "ex madrid destripa ancelotti",
    "basta vergueenza",
    "basta vergüenza",
    "бывший игрок мадрида выпотрошил анчелотти",
    "бывший игрок «мадрида» выпотрошил анчелотти",
    "выпотрошил анчелотти",
    "прорыв эндрика под руководством карло анчелотти",
    "real madrid c mantener plaza segunda rfef",
    "real madrid c mantener",
    "segunda rfef",
    "втором дивизионе рфпл",
    "втором дивизионе rfef",
    "реал c может",
    "xabi alonso told why he decided to lead chelsea",
    "xabi alonso explains why he decided to take over chelsea",
    "nueva etapa asi luce xabi alonso",
    "nueva etapa así luce xabi alonso",
    "xabi alonso primer entrenamiento chelsea",
    "primer entrenamiento con el chelsea",
    "tope del real madrid con vini",
    "tope-real-madrid-vini-cambios-plan-mourinho-decision-clave-fichajes",
    "jude bellingham has ended a world cup debate",
    "ended a world cup debate that should",
    "jurgen klopp kylian mbappe liverpool talks private jet",
    "mbappe liverpool talks private jet",
    "mbappe-liverpool-talks-private-jet",
    "liverpool talks on private jet",
    "talks on private jet psg transfer",
    "какие рекорды уже побил чм-2026",
    "месси, роналду и очоа",
    "real madrid presume cantera espana europeo sub-19",
    "real madrid presume cantera españa europeo sub-19",
    "jose luis sanchez compara bellingham con lamine",
    "compara bellingham con lamine",
    "comercios bernabeu market",
    "comercios bernabéu market",
    "bernabeu market levantan armas",
    "henderson breaks hand",
    "marc guehi receives blow",
    "world-cup-2026-injury-latest-mbappe-henderson-guehi-rice-james",
    "ayyoub bouaddi sent an undeniable transfer guarantee",
    "undeniable transfer guarantee to real madrid",
    "nico paz cumple sueno chiquitito",
    "nico paz cumple sueño chiquitito",
    "lukaku pudo haber llegado real madrid",
    "lukaku pudo haber llegado al real madrid",
    "shakira",
    "shakira le da gracias mbappe",
    "shakira le da gracias a mbappe",
    "shakira le da gracias a mbappé",
    "shakira thanks mbappe",
    "claude makelele throws jude bellingham",
    "impassioned kylian mbappe defense",
    "habi alonso rasskazal pochemu on reshil vozglavit chelsi",
    "хаби алонсо рассказал, почему он решил возглавить челси",
    "хаби алонсо рассказал почему он решил возглавить челси",
    "возглавить челси",
    "george weah",
    "weah said what",
    "fans have been whispering",
    "lamine yamal",
    "джордж веа",
    "ямаля",
    "liga f",
    "grupo pau gasol",
    "pau gasol",
    "chelsea sign italian defender",
    "chelsea signs italian defender",
    "palestra",
    "juanma rodriguez filtros mbappe francia",
    "juanma rodriguez without filters",
    "sin filtros sobre mbappe en francia",
    "mbappe in france",
    "мбаппе в сборной франции",
    "комментарии родригеса",
    "toni kroos got brutally honest",
    "florian wirtz and jamal musiala",
    "wirtz and musiala",
    "jamal musiala stack up with jude bellingham",
    "флориан виртц и джамал музиала",
    "виртц и джамал мусиала",
    "david alaba claro jugar espana",
    "jugar espana especial mi",
    "jugar en espana es especial",
    "jugar en españa es especial",
    "alaba claro: jugar",
    "alaba claro jugar espana",
    "играть в испании особенно",
    "yamal cucurella",
    "lamine yamal cucurella",
    "я его съем",
    "противостоянии с кукурельей",
    "barca copia real madrid desesperada firmar julian alvarez",
    "barca copia al real madrid desesperada firmar",
    "barca copia al real madrid desesperada por firmar",
    "transfer market today",
    "mercado de fichajes hoy",
    "live transfer market",
    "real madrid transfer latest news",
    "latest real madrid transfer news",
    "fichajes real madrid ultimas noticias",
    "fichajes real madrid últimas noticias",
    "fichajes real madrid: ultimas noticias",
    "fichajes real madrid: últimas noticias",
    "fichajes real madrid | ultimas noticias",
    "fichajes real madrid | últimas noticias",
    "mercado fichajes real madrid",
    "mercado de fichajes real madrid",
    "ultimas noticias fichajes",
    "últimas noticias fichajes",
    "рынок трансферов сегодня",
    "в прямом эфире | последние новости",
    "genich",
    "spertsyan",
    "сперцян",
    "генич",
    "ex madrid gente comia poco",
    "gente comia poco",
    "chavales comiamos",
    "бывший житель мадрида",
    "люди ели очень мало",
    "спагетти с помидорами",
    "gareth bale 36 anos",
    "jugue 13 anos con luka modric",
    "гарет бэйл",
    "я играл за луку модрича",
    "keane and gerrard shadows",
    "rooney on bellingham",
    "тени кина и джеррарда",
    "руни",
    "minimum one player in final mundial",
    "menos jugador en final mundial",
    "cuando juegan jugadores real madrid cuartos mundial",
    "cuando juegan los jugadores del real madrid en cuartos",
    "jugadores real madrid cuartos mundial",
    "real madrid players quarter finals world cup",
    "real madrid players world cup quarter finals",
    "siro lopez",
    "siro lópez",
    "me he encontrado en estados unidos",
    "nueva vida en espana con bernardo silva",
    "nueva vida en españa con bernardo silva",
    "минимум одного игрока в финале чемпионата мира",
    "vinicius junior did not hold back after brazil",
    "brazil's inexcusable elimination",
    "brazils inexcusable elimination",
    "винисиус джуниор не сдержался",
    "непростительного удаления бразилии",
    "getting the neymar treatment",
    "курс лечения у неймара",
    "cambio apuestan madridistas",
    "перемены, на которые делают ставку",
    "nobody saw coming",
    "transfer decision nobody saw coming",
    "unexpected transfer decision",
    "неожиданное трансферное решение",
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
    "rincon donde desconecta luka modric",
    "rincón donde desconecta luka modric",
    "comer carne a la brasa",
    "7 minutos del estadio santiago bernabeu",
)

DIGEST_LLM_CLUB_IMPACT_TERMS = (
    "real madrid",
    "official",
    "confirmed",
    "transfer",
    "signing",
    "sign",
    "departure",
    "contract",
    "injury",
    "lineup",
    "squad",
    "fichaje",
    "fichajes",
    "fichar",
    "salida",
    "contrato",
    "lesion",
    "lesión",
    "convocatoria",
    "реал",
    "официально",
    "подтвержден",
    "трансфер",
    "подписание",
    "подписать",
    "подпишет",
    "уход",
    "контракт",
    "травм",
    "состав",
    "заявка",
)


@dataclass
class DigestCandidate:
    title: str
    link: str
    source: str
    published_at: datetime | None
    summary: str = ""


def load_sent_links(path=SENT_FILE):
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_sent_links(links):
    with SENT_FILE.open("w", encoding="utf-8") as f:
        for link in sorted(links):
            f.write(link + "\n")


sent_digest = load_sent_links(SENT_FILE)

TEMPLATES = {
    "утреннего": [
        "<b>Утренние сливки Мадрида</b>\n{intro}\n\n{news}",
        "<b>Белое утро на Бернабеу</b>\n{intro}\n\n{news}",
        "<b>Белый рассвет</b>\n{intro}\n\n{news}",
        "<b>Первый свисток Мадрида</b>\n{intro}\n\n{news}",
        "<b>Утро в Вальдебебасе</b>\n{intro}\n\n{news}",
        "<b>Мадрид просыпается</b>\n{intro}\n\n{news}",
        "<b>Белая лента к утру</b>\n{intro}\n\n{news}",
        "<b>Утренний Бернабеу</b>\n{intro}\n\n{news}",
        "<b>До полудня в Мадриде</b>\n{intro}\n\n{news}",
        "<b>Сливочные новости на старте дня</b>\n{intro}\n\n{news}",
    ],
    "дневного": [
        "<b>К этому часу у сливочных</b>\n{intro}\n\n{news}",
        "<b>Дневная белая сводка</b>\n{intro}\n\n{news}",
        "<b>Белый полдень</b>\n{intro}\n\n{news}",
        "<b>Вальдебебас на связи</b>\n{intro}\n\n{news}",
        "<b>Мадридский радар</b>\n{intro}\n\n{news}",
        "<b>Сливочные вести</b>\n{intro}\n\n{news}",
        "<b>Полдень у «Реала»</b>\n{intro}\n\n{news}",
        "<b>Лента Бернабеу</b>\n{intro}\n\n{news}",
        "<b>Белая перекличка</b>\n{intro}\n\n{news}",
        "<b>Между Вальдебебасом и Бернабеу</b>\n{intro}\n\n{news}",
    ],
    "вечернего": [
        "<b>Вечерняя белая хроника</b>\n{intro}\n\n{news}",
        "<b>Сливочные итоги дня</b>\n{intro}\n\n{news}",
        "<b>Белый вечер в Мадриде</b>\n{intro}\n\n{news}",
        "<b>После заката на Бернабеу</b>\n{intro}\n\n{news}",
        "<b>Закрываем белый день</b>\n{intro}\n\n{news}",
        "<b>Мадридский вечерний рапорт</b>\n{intro}\n\n{news}",
        "<b>Последний свисток дня</b>\n{intro}\n\n{news}",
        "<b>Белая лента перед ночью</b>\n{intro}\n\n{news}",
        "<b>Вечерний Бернабеу</b>\n{intro}\n\n{news}",
        "<b>День по-мадридски: главное</b>\n{intro}\n\n{news}",
    ],
    "ночного": [
        "<b>Ночная смена мадридистов</b>\n{intro}\n\n{news}",
        "<b>Пока Бернабеу спит</b>\n{intro}\n\n{news}",
        "<b>Белая ночь Мадрида</b>\n{intro}\n\n{news}",
        "<b>После полуночи у сливочных</b>\n{intro}\n\n{news}",
        "<b>Ночной Вальдебебас</b>\n{intro}\n\n{news}",
        "<b>Лента, которая не спит</b>\n{intro}\n\n{news}",
    ],
    "default": [
        "<b>Белая сводка «Кофе со сливками»</b>\n{intro}\n\n{news}",
        "<b>Главное о сливочных</b>\n{intro}\n\n{news}",
        "<b>Белая лента Мадрида</b>\n{intro}\n\n{news}",
        "<b>Бернабеу: главное</b>\n{intro}\n\n{news}",
        "<b>Мадридский сбор</b>\n{intro}\n\n{news}",
        "<b>Вести белого Мадрида</b>\n{intro}\n\n{news}",
    ],
}

SHORT_TEMPLATES = {
    "утреннего": [
        "<b>Короткое белое утро</b>\n{intro}\n\n{news}",
        "<b>Утро без лишнего шума</b>\n{intro}\n\n{news}",
        "<b>Утренний белый радар</b>\n{intro}\n\n{news}",
        "<b>Несколько слов о Мадриде</b>\n{intro}\n\n{news}",
        "<b>Первое белое обновление</b>\n{intro}\n\n{news}",
        "<b>Вальдебебас к утру</b>\n{intro}\n\n{news}",
    ],
    "дневного": [
        "<b>Короткая белая сводка</b>\n{intro}\n\n{news}",
        "<b>К этому часу коротко</b>\n{intro}\n\n{news}",
        "<b>Белый полдень: главное</b>\n{intro}\n\n{news}",
        "<b>Дневной радар Мадрида</b>\n{intro}\n\n{news}",
        "<b>Сливочные новости к этому часу</b>\n{intro}\n\n{news}",
        "<b>Бернабеу в нескольких строках</b>\n{intro}\n\n{news}",
    ],
    "вечернего": [
        "<b>Сливочные итоги дня</b>\n{intro}\n\n{news}",
        "<b>Вечерняя белая сводка</b>\n{intro}\n\n{news}",
        "<b>Белый вечер: главное</b>\n{intro}\n\n{news}",
        "<b>Перед ночной паузой</b>\n{intro}\n\n{news}",
        "<b>Мадрид к концу дня</b>\n{intro}\n\n{news}",
        "<b>Вечерний радар Бернабеу</b>\n{intro}\n\n{news}",
    ],
    "ночного": [
        "<b>Ночная короткая сводка</b>\n{intro}\n\n{news}",
        "<b>Ночной белый радар</b>\n{intro}\n\n{news}",
        "<b>Мадрид перед сном</b>\n{intro}\n\n{news}",
    ],
    "default": [
        "<b>Короткая белая сводка</b>\n{intro}\n\n{news}",
        "<b>Белое главное в нескольких строках</b>\n{intro}\n\n{news}",
        "<b>Коротко о сливочных</b>\n{intro}\n\n{news}",
    ],
}

INTRO_LINES = {
    "утреннего": [
        "Свежие новости о «Реале» за ночь и утро.",
        "Что произошло вокруг Мадрида, пока город просыпался.",
    ],
    "дневного": [
        "Главное вокруг клуба к этому часу.",
        "Свежая лента для мадридистов без лишнего шума.",
    ],
    "вечернего": [
        "Собрал главное вокруг Мадрида к вечеру.",
        "Все, что стоит знать о сливочных перед концом дня.",
    ],
    "ночного": [
        "Коротко о том, что не хочется пропустить до утра.",
        "Поздняя белая сводка для тех, кто еще в игре.",
    ],
    "default": [
        "Главное вокруг «Реала» из свежей ленты.",
        "Сливочная подборка без случайного футбольного шума.",
    ],
}

SHORT_INTRO_LINES = {
    "утреннего": [
        "Несколько свежих сюжетов вокруг Мадрида к этому часу.",
        "Коротко по главному из свежей белой ленты.",
    ],
    "дневного": [
        "Несколько важных сюжетов вокруг клуба к этому часу.",
        "Коротко по делу из дневной белой ленты.",
    ],
    "вечернего": [
        "Главное из белой ленты к концу дня.",
        "К вечеру собрались несколько важных сюжетов вокруг клуба.",
    ],
    "ночного": [
        "Поздняя белая лента в коротком формате.",
    ],
    "default": [
        "Коротко по главным сюжетам вокруг «Реала».",
    ],
}

LABEL_ALIASES = {
    "morning": "утреннего",
    "утро": "утреннего",
    "утренний": "утреннего",
    "утреннего": "утреннего",
    "day": "дневного",
    "день": "дневного",
    "дневной": "дневного",
    "дневного": "дневного",
    "evening": "вечернего",
    "вечер": "вечернего",
    "вечерний": "вечернего",
    "вечернего": "вечернего",
    "night": "ночного",
    "ночь": "ночного",
    "ночной": "ночного",
    "ночного": "ночного",
    "auto": "auto",
    "default": "default",
}

LOOKBACK_BY_LABEL = {
    "утреннего": DIGEST_MORNING_LOOKBACK_HOURS,
    "дневного": DIGEST_DAY_LOOKBACK_HOURS,
    "вечернего": DIGEST_EVENING_LOOKBACK_HOURS,
    "ночного": DIGEST_NIGHT_LOOKBACK_HOURS,
    "default": DIGEST_DEFAULT_LOOKBACK_HOURS,
}


def auto_digest_label(now: datetime | None = None) -> str:
    dt = now.astimezone(TZ) if now else datetime.now(TZ)
    hour = dt.hour
    if 5 <= hour < 11:
        return "утреннего"
    if 11 <= hour < 17:
        return "дневного"
    if 17 <= hour <= 23:
        return "вечернего"
    return "ночного"


def normalize_label(label: str | None) -> str:
    if not label:
        return auto_digest_label()
    value = label.strip().lower()
    normalized = LABEL_ALIASES.get(value, value)
    if normalized == "auto":
        return auto_digest_label()
    return normalized


def lookback_hours_for_label(label: str) -> int:
    return LOOKBACK_BY_LABEL.get(label, DIGEST_DEFAULT_LOOKBACK_HOURS)


def entry_published_at(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)

    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    return None


def is_fresh(published_at: datetime | None, cutoff: datetime) -> bool:
    if published_at is None:
        return DIGEST_INCLUDE_UNDATED
    return published_at >= cutoff


def polish_title(title: str) -> str:
    title = clean_text(translate_text(title))

    replacements = {
        "получает диагноз травмы": "узнал диагноз по травме",
        "получил диагноз травмы": "узнал диагноз по травме",
        "диагноз травмы": "диагноз по травме",
        "снова обратился к новой заинтересованности": "снова получил интерес",
        "рекордной плате": "рекордной сумме",
        "новой заинтересованности": "новому интересу",
        "получает новости обратно": "получил новости",
        "Ла Фабриги": "Ла Фабрики",
        "ла фабриги": "Ла Фабрики",
    }
    for bad, good in replacements.items():
        title = title.replace(bad, good)

    return title.strip()


def related_sources_line(item: RankedDigestItem) -> str:
    if not DIGEST_SHOW_RELATED_SOURCES or not item.related_sources:
        return ""

    visible_sources = [escape(source) for source in item.related_sources[:3]]
    extra_count = len(item.related_sources) - len(visible_sources)
    suffix = f" +{extra_count}" if extra_count > 0 else ""
    return f"\nЕще источники: {', '.join(visible_sources)}{suffix}"


def story_label(item: RankedDigestItem) -> str:
    candidate = item.candidate
    # Feed summaries often contain unrelated background context. Topic tags must
    # describe the visible headline, not a stray word deeper in the article.
    text = str(getattr(candidate, "title", "") or "").casefold()

    if any(term in text for term in ("transfer", "fichaje", "traspaso", "mercado", "переход", "трансфер")):
        return "Рынок"
    if any(term in text for term in ("injury", "injured", "lesion", "lesión", "травм", "диагноз")):
        return "Лазарет"
    if any(term in text for term in ("coaching staff", "new staff", "fitness coach", "coach", "manager", "штаб", "тренер")):
        return "Штаб"
    if any(term in text for term in ("lineup", "squad", "convocatoria", "starting xi", "стартовый состав", "заявка")):
        return "Состав"
    if any(
        term in text
        for term in (
            "matchday",
            "preview",
            "derby",
            "clasico",
            "clásico",
            "real madrid vs",
            "real madrid v ",
            "real madrid face",
            "real madrid will face",
            "реал сыграет с",
            "реал играет с",
            "реал против",
            "реал встретится с",
            "матч против",
        )
    ):
        return "Матч-день"
    return ""


STORY_TOPIC_HASHTAGS = {
    "Рынок": "#Трансферы",
    "Лазарет": "#Лазарет",
    "Штаб": "#Штаб",
    "Состав": "#Состав",
    "Матч-день": "#МатчДень",
}


def digest_topic_hashtags(items: list[RankedDigestItem]) -> str:
    """Return each relevant digest topic once, in editorial priority order."""
    seen = set()
    tags = []
    for item in items:
        tag = STORY_TOPIC_HASHTAGS.get(story_label(item))
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return " ".join(tags)


def format_news_entry(i: int, item: RankedDigestItem, title_override: str | None = None) -> str:
    candidate = item.candidate
    safe_text = escape(title_override or polish_title(candidate.title))
    safe_source = escape(candidate.source)
    safe_link = escape(candidate.link, quote=True)
    provenance = source_provenance_label(candidate.source)
    provenance_suffix = f" · {escape(provenance)}" if provenance else ""
    related = related_sources_line(item)
    return f"<b>{i}. {safe_text}</b>\n<a href=\"{safe_link}\">Читать</a> · {safe_source}{provenance_suffix}{related}"


def split_message(message: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if len(message) <= limit:
        return [message]

    chunks: list[str] = []
    current = ""
    for block in message.split("\n\n"):
        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        while len(block) > limit:
            chunks.append(block[:limit])
            block = block[limit:]
        current = block

    if current:
        chunks.append(current)
    return chunks


def already_posted_links() -> set[str]:
    return set(sent_digest) | load_sent_links(SENT_BREAKING_FILE) | published_editorial_links()


def story_fingerprint(title: str, summary: str = "") -> str:
    return ucl_draw_event_key(title, summary, UCL_DRAW_DATE) or semantic_news_key(title, summary)


def digest_semantic_keys(items: list[RankedDigestItem]) -> set[str]:
    keys: set[str] = set()
    for item in items:
        candidate = item.candidate
        key = story_fingerprint(candidate.title, candidate.summary)
        if key:
            keys.add(key)
    return keys


def collect_candidates(sources, cutoff: datetime):
    seen_links = already_posted_links()
    seen_breaking_fingerprints = load_news_keys(SENT_BREAKING_FINGERPRINT_FILE)
    candidates: list[DigestCandidate] = []

    for src in sources:
        url = src.get("url")
        label = src.get("label", url or "Неизвестный источник")
        if not url:
            logging.warning(f"Источник без URL пропущен: {src!r}")
            continue

        try:
            feed = parse_feed_url(src)
            if not feed or not feed.entries:
                continue

            for entry in feed.entries[:DIGEST_ENTRY_SCAN_LIMIT]:
                if source_is_x(src) and is_repost_entry(entry):
                    continue
                link = entry.get("link")
                if not link or link in seen_links:
                    continue

                published_at = entry_published_at(entry)
                if not is_fresh(published_at, cutoff):
                    continue

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "")
                if not title or not passes_filters(title, summary=summary, source=label):
                    continue

                fingerprint = story_fingerprint(title, summary)
                if fingerprint in seen_breaking_fingerprints:
                    logging.info("[DIGEST SKIPPED: BREAKING SEMANTIC DUPLICATE] %s: %s", fingerprint, title)
                    continue

                seen_links.add(link)
                candidates.append(
                    DigestCandidate(
                        title=title,
                        link=link,
                        source=label,
                        published_at=published_at,
                        summary=summary,
                    )
                )
        except Exception as e:
            logging.error(f"Ошибка при парсинге {url}: {e}")

    return candidates


def normalized_similarity_threshold() -> float:
    return min(max(DIGEST_DEDUPE_SIMILARITY, 0), 100) / 100


def load_quarantine() -> list[dict]:
    if not QUARANTINE_FILE.exists():
        return []
    try:
        data = json.loads(QUARANTINE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_quarantine(rows: list[dict]) -> None:
    QUARANTINE_FILE.write_text(
        json.dumps(rows[-QUARANTINE_LIMIT:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_digest_quarantine(candidates: list[DigestCandidate], selected: list[RankedDigestItem], label: str) -> tuple[int, dict[str, int]]:
    selected_links = {item.candidate.link for item in selected}
    now = datetime.now(timezone.utc)
    rows = load_quarantine()
    existing = {row.get("link") for row in rows}
    added = 0
    by_source: dict[str, int] = {}

    for candidate in candidates:
        if candidate.link in selected_links or candidate.link in existing:
            continue
        profile = candidate_profile(candidate, now)
        if profile.score >= 78 and "clickbait" not in profile.reason:
            continue
        rows.append(
            {
                "captured_at": now.isoformat(),
                "label": label,
                "title": candidate.title,
                "link": candidate.link,
                "source": candidate.source,
                "score": profile.score,
                "reason": profile.reason,
            }
        )
        existing.add(candidate.link)
        added += 1
        by_source[candidate.source] = by_source.get(candidate.source, 0) + 1

    if added:
        save_quarantine(rows)
    return added, by_source


def digest_llm_hard_deny(item: RankedDigestItem, headline: str = "") -> bool:
    candidate = item.candidate
    if is_handle_only_x_title(candidate.title, getattr(candidate, "source", "")):
        return True
    text = " ".join(
        [
            str(candidate.title or ""),
            str(getattr(candidate, "summary", "") or ""),
            str(getattr(candidate, "link", "") or ""),
            str(getattr(candidate, "source", "") or ""),
            str(headline or ""),
        ]
    ).casefold()
    if any(term in text for term in DIGEST_LLM_ABSOLUTE_DENY_TERMS):
        return True
    if not any(term in text for term in DIGEST_LLM_HARD_DENY_TERMS):
        return False
    return not any(term in text for term in DIGEST_LLM_CLUB_IMPACT_TERMS)


def apply_digest_hard_deny(selected: list[RankedDigestItem]) -> tuple[list[RankedDigestItem], int]:
    filtered: list[RankedDigestItem] = []
    dropped = 0
    for item in selected:
        if digest_llm_hard_deny(item):
            dropped += 1
            logging.info("[DIGEST HARD DENY] %s | %s", item.candidate.source, item.candidate.title)
            continue
        filtered.append(item)
    if dropped and not filtered:
        logging.warning("[DIGEST HARD DENY] all items were dropped, keeping original selection")
        return selected, 0
    return filtered, dropped


def apply_llm_digest_editor(selected: list[RankedDigestItem], label: str) -> tuple[list[RankedDigestItem], dict[str, str], dict]:
    review_items = []
    for item in selected:
        candidate = item.candidate
        review_items.append(
            {
                "title": candidate.title,
                "source": candidate.source,
                "summary": getattr(candidate, "summary", ""),
                "score": item.score,
                "reason": item.reason,
            }
        )

    result = review_digest_items(review_items, label=label)
    metrics = {
        "llm_editor_used": result.used,
        "llm_editor_reason": result.reason,
        **{f"llm_{key}": value for key, value in result.metrics.items() if key != "error"},
    }
    if not result.used:
        if result.reason not in {"disabled", "empty"}:
            logging.info("[LLM DIGEST] skipped: %s", result.reason)
        selected, hard_dropped = apply_digest_hard_deny(selected)
        metrics["digest_hard_dropped"] = hard_dropped
        return selected, {}, metrics

    filtered: list[RankedDigestItem] = []
    title_overrides: dict[str, str] = {}
    dropped = 0
    for index, item in enumerate(selected, start=1):
        decision = result.decisions.get(index, {})
        if decision.get("keep") is False:
            dropped += 1
            logging.info("[LLM DIGEST] dropped: %s | %s", item.candidate.source, item.candidate.title)
            continue

        headline = str(decision.get("headline_ru") or "").strip()
        cleaned_headline = clean_text(headline) if headline else ""
        if digest_llm_hard_deny(item, headline) or (
            cleaned_headline and digest_llm_hard_deny(item, cleaned_headline)
        ):
            dropped += 1
            logging.info("[LLM DIGEST] hard dropped: %s | %s", item.candidate.source, item.candidate.title)
            continue
        if cleaned_headline:
            title_overrides[item.candidate.link] = cleaned_headline
        filtered.append(item)

    if not filtered:
        logging.warning("[LLM DIGEST] all items were dropped, keeping original selection")
        metrics["llm_editor_all_dropped"] = True
        return selected, {}, metrics

    metrics["llm_editor_dropped"] = dropped
    metrics["llm_editor_titles"] = len(title_overrides)
    return filtered, title_overrides, metrics


def fetch_digest(sources, label: str, limit=DIGEST_LIMIT):
    lookback_hours = lookback_hours_for_label(label)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    candidates = collect_candidates(sources, cutoff)
    candidates.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    review_limit = max(limit, LLM_EDITOR_MAX_DIGEST_ITEMS)
    selected = rank_digest_candidates(
        candidates,
        limit=review_limit,
        dedupe_enabled=DIGEST_DEDUPE_ENABLED,
        priority_sort_enabled=DIGEST_PRIORITY_SORT_ENABLED,
        similarity_threshold=normalized_similarity_threshold(),
    )
    selected, title_overrides, editor_metrics = apply_llm_digest_editor(selected, label)
    selected = selected[:limit]
    quarantined, quarantined_by_source = update_digest_quarantine(candidates, selected, label)
    source_quality = update_digest_source_quality(
        sources=sources,
        candidates=candidates,
        selected=selected,
        quarantined_by_source=quarantined_by_source,
    )
    news_items = [
        format_news_entry(i, item, title_overrides.get(item.candidate.link))
        for i, item in enumerate(selected, start=1)
    ]
    new_links = set()
    grouped_links = 0
    for item in selected:
        new_links.update(item.grouped_links)
        grouped_links += max(len(item.grouped_links) - 1, 0)
    new_fingerprints = digest_semantic_keys(selected)

    logging.info(
        "Digest label=%s lookback=%sh candidates=%s selected=%s grouped=%s priority_sort=%s dedupe=%s",
        label,
        lookback_hours,
        len(candidates),
        len(selected),
        grouped_links,
        DIGEST_PRIORITY_SORT_ENABLED,
        DIGEST_DEDUPE_ENABLED,
    )
    metrics = {
        "label": label,
        "lookback_hours": lookback_hours,
        "candidates": len(candidates),
        "selected": len(selected),
        "review_limit": review_limit,
        "grouped_links": grouped_links,
        "dedupe": DIGEST_DEDUPE_ENABLED,
        "priority_sort": DIGEST_PRIORITY_SORT_ENABLED,
        "quarantined": quarantined,
        "semantic_keys": len(new_fingerprints),
        "source_quality": {
            "tracked_sources": source_quality.get("tracked_sources", 0),
            "noisy": source_quality.get("noisy", [])[:3],
            "quiet": source_quality.get("quiet", [])[:3],
        },
        **editor_metrics,
    }
    return news_items, new_links, new_fingerprints, metrics, selected, title_overrides


def digest_render_plan(label: str, item_count: int) -> tuple[str, list[str], list[str]]:
    if item_count < DIGEST_SHORT_FORMAT_THRESHOLD:
        return (
            "short",
            SHORT_TEMPLATES.get(label, SHORT_TEMPLATES["default"]),
            SHORT_INTRO_LINES.get(label, SHORT_INTRO_LINES["default"]),
        )
    return "full", TEMPLATES.get(label, TEMPLATES["default"]), INTRO_LINES.get(label, INTRO_LINES["default"])


def load_template_history() -> dict[str, list[str]]:
    if not TEMPLATE_HISTORY_FILE.exists():
        return {}
    try:
        data = json.loads(TEMPLATE_HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(label): [str(template) for template in history if isinstance(template, str)]
        for label, history in data.items()
        if isinstance(history, list)
    }


def save_template_history(history: dict[str, list[str]]) -> None:
    TEMPLATE_HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def pick_template_without_recent_repeats(templates: list[str], recent: list[str]) -> str:
    if not templates:
        raise ValueError("Digest template list must not be empty")
    blocked = set(recent[-TEMPLATE_HISTORY_LIMIT:])
    available = [template for template in templates if template not in blocked]
    return random.choice(available or templates)


def choose_digest_template(label: str, templates: list[str]) -> str:
    history = load_template_history()
    recent = history.get(label, [])
    template = pick_template_without_recent_repeats(templates, recent)
    history[label] = (recent + [template])[-TEMPLATE_HISTORY_LIMIT:]
    save_template_history(history)
    return template


def post_telegram_message(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    for attempt in range(1, 4):
        try:
            response = requests.post(url, data=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)
            if response.status_code == 200:
                return True
            logging.error("Ошибка Telegram API: %s %s", response.status_code, response.text)
        except requests.RequestException as exc:
            logging.error("Ошибка при отправке дайджеста, попытка %s: %s", attempt, exc)

        if attempt < 3:
            time.sleep(attempt * 2)

    return False


def post_telegram_photo(caption: str, photo_path) -> bool:
    if len(caption) > 1024 or not photo_path:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "caption": caption,
        "parse_mode": "HTML",
    }
    for attempt in range(1, 3):
        try:
            with open(photo_path, "rb") as image_file:
                response = requests.post(
                    url,
                    data=payload,
                    files={"photo": (photo_path.name, image_file, "image/jpeg")},
                    timeout=TELEGRAM_TIMEOUT_SECONDS,
                )
            if response.status_code == 200:
                return True
            logging.warning("Фирменная карточка дайджеста не отправилась: %s %s", response.status_code, response.text)
        except (OSError, requests.RequestException) as exc:
            logging.warning("Ошибка карточки дайджеста, попытка %s: %s", attempt, exc)
        if attempt < 2:
            time.sleep(attempt * 2)
    return False


def send_digest(label: str = "auto"):
    global sent_digest

    label = normalize_label(label)
    record_status("digest", "starting", "digest run started", {"label": label, "dry_run": DRY_RUN})
    block_reason = digest_block_reason()
    if block_reason:
        metrics = {"label": label, "reason": block_reason}
        record_status("digest", "skipped", block_reason, metrics)
        logging.info("Дайджест %s пропущен: %s", label, block_reason)
        print(f"[DIGEST] Пропущен: {block_reason}")
        return

    sources = SOURCES_INTERNATIONAL + SOURCES_RU
    news_items, new_links, new_fingerprints, metrics, selected_items, title_overrides = fetch_digest(
        sources,
        label=label,
        limit=DIGEST_LIMIT,
    )
    metrics["dry_run"] = DRY_RUN

    if not news_items:
        record_status("digest", "empty", f"Нет свежих новостей для {label} дайджеста", metrics)
        logging.info(f"Нет свежих новостей для {label} дайджеста")
        print(f"[DIGEST] Нет свежих новостей для {label} дайджеста")
        return

    if len(news_items) < DIGEST_MIN_ITEMS_TO_POST:
        metrics["format"] = "skipped_thin"
        metrics["min_items_to_post"] = DIGEST_MIN_ITEMS_TO_POST
        record_status("digest", "skipped", f"Слишком тонкая лента для {label} дайджеста", metrics)
        logging.info("Дайджест %s пропущен: слишком мало новостей (%s)", label, len(news_items))
        print(f"[DIGEST] Пропущен {label}: слишком мало новостей ({len(news_items)})")
        return

    joined_news = "\n\n".join(news_items)
    render_format, templates, intro_lines = digest_render_plan(label, len(news_items))
    metrics["format"] = render_format
    metrics["short_format_threshold"] = DIGEST_SHORT_FORMAT_THRESHOLD
    intro = random.choice(intro_lines)
    template = choose_digest_template(label, templates)
    message = template.format(news=joined_news, intro=intro)
    topic_hashtags = digest_topic_hashtags(selected_items)
    message = append_hashtags(message, f"{DIGEST_HASHTAGS} {topic_hashtags}")
    metrics["topic_hashtags"] = topic_hashtags
    chunks = split_message(message)
    metrics["chunks"] = len(chunks)
    metrics["new_links"] = len(new_links)

    if DRY_RUN:
        record_status("digest", "dry_run", f"{label} digest rendered", metrics)
        logging.info(f"DRY_RUN {label} дайджест: {len(news_items)} новостей, частей: {len(chunks)}")
        print(f"[DRY RUN DIGEST: {label}]")
        for index, chunk in enumerate(chunks, start=1):
            print(f"\n--- часть {index}/{len(chunks)} ---\n{chunk}")
        return

    if not telegram_configured():
        record_error("digest", "TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы", metrics)
        logging.error("TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        return

    sent_with_card = False
    if len(chunks) == 1 and len(chunks[0]) <= 1024:
        card_path = render_news_card()
        sent_with_card = post_telegram_photo(chunks[0], card_path)
        if sent_with_card:
            metrics["visual_card"] = True

    for index, chunk in enumerate(chunks):
        if sent_with_card and index == 0:
            continue
        if not post_telegram_message(chunk):
            record_error("digest", "Дайджест не сохранен как отправленный: часть сообщения не дошла", metrics)
            logging.error("Дайджест не сохранен как отправленный: часть сообщения не дошла")
            return

    sent_digest.update(new_links)
    save_sent_links(sent_digest)
    if new_fingerprints:
        sent_fingerprints = load_news_keys(SENT_BREAKING_FINGERPRINT_FILE)
        sent_fingerprints.update(new_fingerprints)
        save_news_keys(SENT_BREAKING_FINGERPRINT_FILE, sent_fingerprints)
    archive_digest_items(label, selected_items, title_overrides)
    record_status("digest", "ok", f"Опубликован {label} дайджест", metrics)
    logging.info(f"Опубликован {label} дайджест")


if __name__ == "__main__":
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else "auto"
    send_digest(arg)
