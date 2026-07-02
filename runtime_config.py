import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def _resolve_dir(value: str) -> Path:
    return _resolve_path(value)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def env_csv(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]


def env_int_list(name: str, default: str) -> list[int]:
    values = []
    for part in env_csv(name, default):
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values


DRY_RUN = env_bool("DRY_RUN", default=True)
STATE_DIR = _resolve_dir(os.getenv("STATE_DIR", "state"))
LOG_DIR = _resolve_dir(os.getenv("LOG_DIR", "logs"))
STATUS_FILE = _resolve_path(os.getenv("STATUS_FILE", str(STATE_DIR / "status.json")))
BREAKING_INTERVAL_SECONDS = env_int("BREAKING_INTERVAL_SECONDS", 120)
HEARTBEAT_HOST = os.getenv("HEARTBEAT_HOST", "127.0.0.1")
HEARTBEAT_PORT = env_int("HEARTBEAT_PORT", 8000)
HEARTBEAT_TOKEN = os.getenv("HEARTBEAT_TOKEN", "").strip()
HEARTBEAT_MAIN_STALE_SECONDS = env_int("HEARTBEAT_MAIN_STALE_SECONDS", 180)
HEARTBEAT_BREAKING_STALE_SECONDS = env_int(
    "HEARTBEAT_BREAKING_STALE_SECONDS",
    max(BREAKING_INTERVAL_SECONDS * 3 + 60, 300),
)
PREFLIGHT_STATUS_TTL_SECONDS = env_int("PREFLIGHT_STATUS_TTL_SECONDS", 1800)

HTTP_USER_AGENT = os.getenv(
    "HTTP_USER_AGENT",
    "CoffeeBot/1.0 (+https://t.me/slivochniyfootball)",
)
RSS_TIMEOUT_SECONDS = env_int("RSS_TIMEOUT_SECONDS", 15)
TELEGRAM_TIMEOUT_SECONDS = env_int("TELEGRAM_TIMEOUT_SECONDS", 10)
TELEGRAM_MESSAGE_LIMIT = env_int("TELEGRAM_MESSAGE_LIMIT", 3900)

POST_HASHTAGS = os.getenv("POST_HASHTAGS", "#RealMadrid #HalaMadrid #КофеСоСливками")
DIGEST_HASHTAGS = os.getenv("DIGEST_HASHTAGS", f"{POST_HASHTAGS} #Дайджест")
BREAKING_HASHTAGS = os.getenv("BREAKING_HASHTAGS", f"{POST_HASHTAGS} #СливочнаяМолния")
MATCHDAY_HASHTAGS = os.getenv("MATCHDAY_HASHTAGS", f"{POST_HASHTAGS} #МатчДень")
LIVE_HASHTAGS = os.getenv("LIVE_HASHTAGS", f"{POST_HASHTAGS} #Live #МатчДень")

DIGEST_TIMEZONE = os.getenv("DIGEST_TIMEZONE", "Europe/Moscow")
DIGEST_MORNING_TIME = os.getenv("DIGEST_MORNING_TIME", "09:00")
DIGEST_DAY_TIME = os.getenv("DIGEST_DAY_TIME", "15:00")
DIGEST_EVENING_TIME = os.getenv("DIGEST_EVENING_TIME", "21:00")
DIGEST_MISSED_CATCHUP_ENABLED = env_bool("DIGEST_MISSED_CATCHUP_ENABLED", default=True)
DIGEST_MISSED_GRACE_MINUTES = env_int("DIGEST_MISSED_GRACE_MINUTES", 360)
DIGEST_LIMIT = env_int("DIGEST_LIMIT", 10)
DIGEST_ENTRY_SCAN_LIMIT = env_int("DIGEST_ENTRY_SCAN_LIMIT", 5)
DIGEST_DEFAULT_LOOKBACK_HOURS = env_int("DIGEST_DEFAULT_LOOKBACK_HOURS", 8)
DIGEST_MORNING_LOOKBACK_HOURS = env_int("DIGEST_MORNING_LOOKBACK_HOURS", 14)
DIGEST_DAY_LOOKBACK_HOURS = env_int("DIGEST_DAY_LOOKBACK_HOURS", 8)
DIGEST_EVENING_LOOKBACK_HOURS = env_int("DIGEST_EVENING_LOOKBACK_HOURS", 8)
DIGEST_NIGHT_LOOKBACK_HOURS = env_int("DIGEST_NIGHT_LOOKBACK_HOURS", 8)
DIGEST_INCLUDE_UNDATED = env_bool("DIGEST_INCLUDE_UNDATED", default=False)
DIGEST_DEDUPE_ENABLED = env_bool("DIGEST_DEDUPE_ENABLED", default=True)
DIGEST_PRIORITY_SORT_ENABLED = env_bool("DIGEST_PRIORITY_SORT_ENABLED", default=True)
DIGEST_SHOW_RELATED_SOURCES = env_bool("DIGEST_SHOW_RELATED_SOURCES", default=True)
DIGEST_DEDUPE_SIMILARITY = env_int("DIGEST_DEDUPE_SIMILARITY", 42)
DIGEST_PREFLIGHT_ENABLED = env_bool("DIGEST_PREFLIGHT_ENABLED", default=True)
DIGEST_PREFLIGHT_MINUTES = env_int("DIGEST_PREFLIGHT_MINUTES", 5)
DIGEST_PREFLIGHT_WARN_MIN_CANDIDATES = env_int("DIGEST_PREFLIGHT_WARN_MIN_CANDIDATES", 6)

MATCHDAY_ENABLED = env_bool("MATCHDAY_ENABLED", default=True)
MATCH_SCHEDULE_FILE = _resolve_path(os.getenv("MATCH_SCHEDULE_FILE", "config/matches.json"))
MATCHDAY_BLOCK_BEFORE_HOURS = env_int("MATCHDAY_BLOCK_BEFORE_HOURS", 3)
MATCHDAY_BLOCK_AFTER_HOURS = env_int("MATCHDAY_BLOCK_AFTER_HOURS", 2)
MATCHDAY_BLOCK_ALL_DAY = env_bool("MATCHDAY_BLOCK_ALL_DAY", default=False)
MATCHDAY_PREVIEW_MINUTES = env_int("MATCHDAY_PREVIEW_MINUTES", 60)
MATCHDAY_HALFTIME_MINUTES = env_int("MATCHDAY_HALFTIME_MINUTES", 50)
MATCHDAY_FULLTIME_MINUTES = env_int("MATCHDAY_FULLTIME_MINUTES", 125)
MATCHDAY_POST_TOLERANCE_MINUTES = env_int("MATCHDAY_POST_TOLERANCE_MINUTES", 20)
MATCHDAY_POLL_SECONDS = env_int("MATCHDAY_POLL_SECONDS", 60)
HEARTBEAT_MATCHDAY_STALE_SECONDS = env_int(
    "HEARTBEAT_MATCHDAY_STALE_SECONDS",
    max(MATCHDAY_POLL_SECONDS * 5 + 60, 600),
)

MATCHDAY_LIVE_ENABLED = env_bool("MATCHDAY_LIVE_ENABLED", default=False)
MATCHDAY_LIVE_PROVIDER = os.getenv("MATCHDAY_LIVE_PROVIDER", "api-football").strip().lower()
MATCHDAY_LIVE_POLL_SECONDS = env_int("MATCHDAY_LIVE_POLL_SECONDS", 180)
MATCHDAY_LIVE_BEFORE_MINUTES = env_int("MATCHDAY_LIVE_BEFORE_MINUTES", 15)
MATCHDAY_LIVE_AFTER_MINUTES = env_int("MATCHDAY_LIVE_AFTER_MINUTES", 30)
MATCHDAY_LIVE_EVENT_TYPES = {part.casefold() for part in env_csv("MATCHDAY_LIVE_EVENT_TYPES", "Goal,Card,subst,Var")}
HEARTBEAT_LIVE_STALE_SECONDS = env_int(
    "HEARTBEAT_LIVE_STALE_SECONDS",
    max(MATCHDAY_LIVE_POLL_SECONDS * 3 + 60, 900),
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY") or os.getenv("APISPORTS_KEY")
API_FOOTBALL_BASE_URL = os.getenv("API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io").rstrip("/")
API_FOOTBALL_TEAM_ID = env_int("API_FOOTBALL_TEAM_ID", 541)
API_FOOTBALL_LEAGUE_IDS = env_int_list("API_FOOTBALL_LEAGUE_IDS", "140,2")
API_FOOTBALL_REQUEST_TIMEOUT_SECONDS = env_int("API_FOOTBALL_REQUEST_TIMEOUT_SECONDS", 10)

YANDEX_LLM_ENABLED = env_bool("YANDEX_LLM_ENABLED", default=False)
YANDEX_LLM_API_KEY = (
    os.getenv("YANDEX_LLM_API_KEY")
    or os.getenv("YANDEX_TRANSLATE_API_KEY")
    or os.getenv("YANDEX_API_KEY")
)
YANDEX_LLM_FOLDER_ID = os.getenv("YANDEX_LLM_FOLDER_ID") or os.getenv("YANDEX_FOLDER_ID")
YANDEX_LLM_MODEL = os.getenv("YANDEX_LLM_MODEL", "yandexgpt-lite")
YANDEX_LLM_URL = os.getenv(
    "YANDEX_LLM_URL",
    "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
)
YANDEX_LLM_TIMEOUT_SECONDS = env_int("YANDEX_LLM_TIMEOUT_SECONDS", 20)
YANDEX_LLM_MAX_TOKENS = env_int("YANDEX_LLM_MAX_TOKENS", 900)
YANDEX_LLM_TEMPERATURE = env_float("YANDEX_LLM_TEMPERATURE", 0.1)

LLM_EDITOR_DIGEST_ENABLED = env_bool("LLM_EDITOR_DIGEST_ENABLED", default=True)
LLM_EDITOR_BREAKING_ENABLED = env_bool("LLM_EDITOR_BREAKING_ENABLED", default=True)
LLM_EDITOR_DAILY_REQUEST_LIMIT = env_int("LLM_EDITOR_DAILY_REQUEST_LIMIT", 60)
LLM_EDITOR_DAILY_CHAR_LIMIT = env_int("LLM_EDITOR_DAILY_CHAR_LIMIT", 150000)
LLM_EDITOR_MAX_DIGEST_ITEMS = env_int("LLM_EDITOR_MAX_DIGEST_ITEMS", 14)
LLM_EDITOR_MAX_BREAKING_ITEMS = env_int("LLM_EDITOR_MAX_BREAKING_ITEMS", 10)
LLM_EDITOR_MAX_SUMMARY_CHARS = env_int("LLM_EDITOR_MAX_SUMMARY_CHARS", 240)
LLM_EDITOR_BREAKING_BUFFER_SECONDS = env_int("LLM_EDITOR_BREAKING_BUFFER_SECONDS", 600)
LLM_EDITOR_BREAKING_MIN_INTERVAL_SECONDS = env_int("LLM_EDITOR_BREAKING_MIN_INTERVAL_SECONDS", 600)
LLM_EDITOR_BREAKING_FALLBACK_AFTER_SECONDS = env_int("LLM_EDITOR_BREAKING_FALLBACK_AFTER_SECONDS", 3600)
BREAKING_PREFLIGHT_PENDING_WARN = env_int("BREAKING_PREFLIGHT_PENDING_WARN", LLM_EDITOR_MAX_BREAKING_ITEMS)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_state_file(name: str) -> Path:
    return STATE_DIR / name


def get_log_file(name: str) -> Path:
    return LOG_DIR / name


def telegram_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TARGET_CHAT_ID)
