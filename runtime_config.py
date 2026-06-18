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
BREAKING_INTERVAL_SECONDS = env_int("BREAKING_INTERVAL_SECONDS", 120)
HEARTBEAT_PORT = env_int("HEARTBEAT_PORT", 8000)

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

MATCHDAY_LIVE_ENABLED = env_bool("MATCHDAY_LIVE_ENABLED", default=False)
MATCHDAY_LIVE_PROVIDER = os.getenv("MATCHDAY_LIVE_PROVIDER", "api-football").strip().lower()
MATCHDAY_LIVE_POLL_SECONDS = env_int("MATCHDAY_LIVE_POLL_SECONDS", 180)
MATCHDAY_LIVE_BEFORE_MINUTES = env_int("MATCHDAY_LIVE_BEFORE_MINUTES", 15)
MATCHDAY_LIVE_AFTER_MINUTES = env_int("MATCHDAY_LIVE_AFTER_MINUTES", 30)
MATCHDAY_LIVE_EVENT_TYPES = {part.casefold() for part in env_csv("MATCHDAY_LIVE_EVENT_TYPES", "Goal,Card,subst,Var")}

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY") or os.getenv("APISPORTS_KEY")
API_FOOTBALL_BASE_URL = os.getenv("API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io").rstrip("/")
API_FOOTBALL_TEAM_ID = env_int("API_FOOTBALL_TEAM_ID", 541)
API_FOOTBALL_LEAGUE_IDS = env_int_list("API_FOOTBALL_LEAGUE_IDS", "140,2")
API_FOOTBALL_REQUEST_TIMEOUT_SECONDS = env_int("API_FOOTBALL_REQUEST_TIMEOUT_SECONDS", 10)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_state_file(name: str) -> Path:
    return STATE_DIR / name


def get_log_file(name: str) -> Path:
    return LOG_DIR / name


def telegram_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TARGET_CHAT_ID)
