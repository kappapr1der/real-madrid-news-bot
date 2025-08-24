import os
from loguru import logger
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

PROJECT_NAME = "☕ Кофе со сливками — Новости Реала"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")

LOG_FILE = os.path.join(BASE_DIR, "coffee_bot.log")
logger.add(LOG_FILE, rotation="10 MB", retention="7 days", level="INFO", encoding="utf-8")

BLACKLIST = ["matchcenter", "тизер", "трансляция", "stream", "betting", "prediction"]

ALLOWED_DOMAINS = ["realmadrid.com", "marca.com", "as.com", "defensacentral.com", "managingmadrid.com"]

TRANSLATION_PRIORITY = ["deep-translator", "mymemory"]
DEFAULT_LANG = "ru"

CHECK_INTERVAL = 60
DIGEST_INTERVAL = 3600
HEARTBEAT_INTERVAL = 300

HEADER_EMOJI = "☕⚪"
BREAKING_EMOJI = "🚨"
DIGEST_EMOJI = "📋"

POST_TEMPLATE = """{emoji} <b>{title}</b>
{summary}
<a href='{url}'>Источник</a>"""

DIGEST_TEMPLATE = """{emoji} <b>Дайджест новостей</b>

{items}

<i>Сливочный обзор — только лучшее за час.</i>
"""

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
HEARTBEAT_NAME = "⚪ Сердце Бернабеу"

logger.info("Конфигурация успешно загружена ✅")
