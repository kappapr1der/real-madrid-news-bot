import logging
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
import yaml
from deep_translator import GoogleTranslator, MyMemoryTranslator
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

HERE = Path(__file__).parent
DEFAULT_TERMS_PATH = HERE / "terms_by_theme.yaml"
DEFAULT_ADDITIONS = HERE / "additions.yaml"

TERMS_PATH = Path(os.getenv("TERMS_PATH", str(DEFAULT_TERMS_PATH)))
TERMS_ADDITIONS_ENV = os.getenv("TERMS_ADDITIONS")
ADDITIONS_PATHS: List[Path] = []

YANDEX_TRANSLATE_API_KEY = os.getenv("YANDEX_TRANSLATE_API_KEY") or os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
YANDEX_TRANSLATE_URL = os.getenv(
    "YANDEX_TRANSLATE_URL",
    "https://translate.api.cloud.yandex.net/translate/v2/translate",
)

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
DEEPL_API_URL = os.getenv("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate")

TRANSLATION_STATS_PATH = Path(
    os.getenv("TRANSLATION_STATS_PATH", str(HERE / "state" / "translation_stats.json"))
)

if TERMS_ADDITIONS_ENV:
    ADDITIONS_PATHS = [Path(p.strip()) for p in TERMS_ADDITIONS_ENV.split(",") if p.strip()]
elif DEFAULT_ADDITIONS.exists():
    ADDITIONS_PATHS = [DEFAULT_ADDITIONS]


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path or not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: Any, add: Any) -> Any:
    if base is None:
        return add
    if add is None:
        return base
    if isinstance(base, dict) and isinstance(add, dict):
        res = dict(base)
        for k, v in add.items():
            res[k] = _deep_merge(res.get(k), v)
        return res
    if isinstance(base, list) and isinstance(add, list):
        seen = set(base)
        res = list(base)
        for item in add:
            if item not in seen:
                res.append(item)
                seen.add(item)
        return res
    return add


SECTION_ORDER = [
    "typos",
    "names",
    "clubs",
    "competitions",
    "positions",
    "terms",
    "phrases",
    "templates",
]


def _build_literal_pattern(key: str) -> re.Pattern:
    escaped = re.escape(key)
    if len(key) <= 3:
        pat = rf"\b{escaped}\b"
    else:
        pat = escaped
    return re.compile(pat, re.IGNORECASE | re.DOTALL)


def _compile_replacements(data: Dict[str, Dict[str, str]]) -> List[Tuple[str, re.Pattern, str]]:
    compiled: List[Tuple[str, re.Pattern, str]] = []
    for section in SECTION_ORDER:
        mapping: Dict[str, str] = data.get(section, {}) or {}
        items = sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True)
        for key, val in items:
            if not key:
                continue
            if section == "phrases":
                try:
                    pat = re.compile(key, re.IGNORECASE | re.DOTALL)
                except re.error as e:
                    logger.warning(f"[TERMS] Некорректный regex в phrases: '{key}': {e}")
                    continue
            else:
                pat = _build_literal_pattern(key)
            compiled.append((section, pat, val))
    return compiled


def _load_terms_merged() -> Dict[str, Dict[str, str]]:
    if not TERMS_PATH.exists():
        logger.warning("terms_by_theme.yaml not found")
        base = {}
    else:
        base = _load_yaml(TERMS_PATH)

    merged = dict(base)
    for add_path in ADDITIONS_PATHS:
        add = _load_yaml(add_path)
        if add:
            merged = _deep_merge(merged, add)
            logger.info(f"[TERMS] Merged additions: {add_path.name}")
        else:
            logger.info(f"[TERMS] Additions empty or missing: {add_path}")

    out: Dict[str, Dict[str, str]] = {sec: dict(merged.get(sec, {}) or {}) for sec in SECTION_ORDER}
    for sec, mapping in merged.items():
        if sec not in out and isinstance(mapping, dict):
            out[sec] = dict(mapping)
    return out


_RAW_TERMS = _load_terms_merged()
_COMPILED_REPLACEMENTS = _compile_replacements(_RAW_TERMS)


def apply_custom_dictionary(text: str) -> str:
    if not text:
        return text

    result = text
    touched: List[str] = []

    for section, pattern, repl in _COMPILED_REPLACEMENTS:
        new_text, count = pattern.subn(repl, result)
        if count > 0:
            touched.append(f"{section}: '{pattern.pattern}' -> '{repl}' (x{count})")
            result = new_text

    if touched:
        logger.info("[TERMS] Заменены термины:\n  - " + "\n  - ".join(touched))

    return result


def _translate_with_yandex(text: str) -> str | None:
    if not (YANDEX_TRANSLATE_API_KEY and YANDEX_FOLDER_ID):
        return None

    response = requests.post(
        YANDEX_TRANSLATE_URL,
        headers={
            "Authorization": f"Api-Key {YANDEX_TRANSLATE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "folderId": YANDEX_FOLDER_ID,
            "texts": [text],
            "targetLanguageCode": "ru",
        },
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    translations = payload.get("translations") or []
    if not translations:
        return None
    return translations[0].get("text")


def _translate_with_deepl(text: str) -> str | None:
    if not DEEPL_API_KEY:
        return None

    response = requests.post(
        DEEPL_API_URL,
        data={
            "auth_key": DEEPL_API_KEY,
            "text": text,
            "target_lang": "RU",
            "preserve_formatting": "1",
        },
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    translations = payload.get("translations") or []
    if not translations:
        return None
    return translations[0].get("text")


def _translate_with_google(text: str) -> str:
    return GoogleTranslator(source="auto", target="ru").translate(text)


def _translate_with_mymemory(text: str) -> str:
    return MyMemoryTranslator(source="auto", target="ru").translate(text)


def _record_translation(provider: str, input_chars: int, status: str = "ok", error: str | None = None) -> None:
    now = int(time.time())
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        data: Dict[str, Any] = {}
        if TRANSLATION_STATS_PATH.exists():
            data = json.loads(TRANSLATION_STATS_PATH.read_text(encoding="utf-8") or "{}")

        providers: Dict[str, Any] = data.setdefault("providers", {})
        bucket: Dict[str, Any] = providers.setdefault(
            provider,
            {"ok_calls": 0, "error_calls": 0, "input_chars": 0},
        )

        if status == "ok":
            bucket["ok_calls"] = int(bucket.get("ok_calls", 0)) + 1
            data["last_ok_provider"] = provider
            data["last_ok_at"] = now
        else:
            bucket["error_calls"] = int(bucket.get("error_calls", 0)) + 1
            bucket["last_error"] = (error or "")[:200]
            data["last_error_provider"] = provider
            data["last_error_at"] = now

        bucket["input_chars"] = int(bucket.get("input_chars", 0)) + max(input_chars, 0)
        bucket["last_at"] = now

        days: Dict[str, Any] = data.setdefault("days", {})
        day_bucket: Dict[str, Any] = days.setdefault(
            day,
            {"ok_calls": 0, "error_calls": 0, "input_chars": 0, "providers": {}},
        )
        day_provider: Dict[str, Any] = day_bucket.setdefault("providers", {}).setdefault(
            provider,
            {"ok_calls": 0, "error_calls": 0, "input_chars": 0},
        )
        if status == "ok":
            day_bucket["ok_calls"] = int(day_bucket.get("ok_calls", 0)) + 1
            day_provider["ok_calls"] = int(day_provider.get("ok_calls", 0)) + 1
        else:
            day_bucket["error_calls"] = int(day_bucket.get("error_calls", 0)) + 1
            day_provider["error_calls"] = int(day_provider.get("error_calls", 0)) + 1
            day_provider["last_error"] = (error or "")[:200]
        day_bucket["input_chars"] = int(day_bucket.get("input_chars", 0)) + max(input_chars, 0)
        day_provider["input_chars"] = int(day_provider.get("input_chars", 0)) + max(input_chars, 0)
        day_provider["last_at"] = now
        data["current_day"] = day
        data["total_events"] = int(data.get("total_events", 0)) + 1
        data["total_input_chars"] = int(data.get("total_input_chars", 0)) + max(input_chars, 0)

        TRANSLATION_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = TRANSLATION_STATS_PATH.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(TRANSLATION_STATS_PATH)
    except Exception as exc:
        logger.warning(f"[TRANSLATE] Stats write failed: {exc}")


def translate_text(text: str) -> str:
    """
    1) Yandex Translate, if YANDEX_TRANSLATE_API_KEY and YANDEX_FOLDER_ID are configured
    2) DeepL API Free, if DEEPL_API_KEY is configured
    3) GoogleTranslator
    4) MyMemoryTranslator
    5) original text

    Then apply the local football dictionary.
    """
    translated = None
    provider = None
    input_chars = len(text or "")

    if YANDEX_TRANSLATE_API_KEY and YANDEX_FOLDER_ID:
        try:
            translated = _translate_with_yandex(text)
            if translated:
                provider = "yandex"
        except Exception as e:
            logger.error(f"Yandex Translate error: {e}")
            _record_translation("yandex", input_chars, status="error", error=str(e))

    if not translated and DEEPL_API_KEY:
        try:
            translated = _translate_with_deepl(text)
            if translated:
                provider = "deepl"
        except Exception as e:
            logger.error(f"DeepL error: {e}")
            _record_translation("deepl", input_chars, status="error", error=str(e))

    if not translated:
        try:
            translated = _translate_with_google(text)
            if translated:
                provider = "google"
        except Exception as e:
            logger.error(f"GoogleTranslator error: {e}")
            _record_translation("google", input_chars, status="error", error=str(e))

    if not translated:
        try:
            translated = _translate_with_mymemory(text)
            if translated:
                provider = "mymemory"
        except Exception as e:
            logger.error(f"MyMemoryTranslator error: {e}")
            _record_translation("mymemory", input_chars, status="error", error=str(e))

    if not translated:
        translated = text
        provider = "original"

    _record_translation(provider or "unknown", input_chars)
    logger.info("[TRANSLATE] provider=%s chars=%s", provider or "unknown", input_chars)
    return apply_custom_dictionary(translated)
