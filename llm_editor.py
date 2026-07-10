import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from runtime_config import (
    LLM_EDITOR_BREAKING_ENABLED,
    LLM_EDITOR_BREAKING_MIN_INTERVAL_SECONDS,
    LLM_EDITOR_DAILY_CHAR_LIMIT,
    LLM_EDITOR_DAILY_REQUEST_LIMIT,
    LLM_EDITOR_DIGEST_ENABLED,
    LLM_EDITOR_MAX_BREAKING_ITEMS,
    LLM_EDITOR_MAX_DIGEST_ITEMS,
    LLM_EDITOR_MAX_SUMMARY_CHARS,
    YANDEX_LLM_API_KEY,
    YANDEX_LLM_ENABLED,
    YANDEX_LLM_FOLDER_ID,
    YANDEX_LLM_MAX_TOKENS,
    YANDEX_LLM_MODEL,
    YANDEX_LLM_TEMPERATURE,
    YANDEX_LLM_TIMEOUT_SECONDS,
    YANDEX_LLM_URL,
    get_state_file,
)
from source_quality import source_trust_tier

logger = logging.getLogger(__name__)

STATS_FILE = get_state_file("llm_editor_stats.json")


@dataclass
class LLMReviewResult:
    used: bool
    reason: str = ""
    decisions: dict[int, dict[str, Any]] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


def llm_editor_enabled(kind: str | None = None) -> bool:
    if not YANDEX_LLM_ENABLED:
        return False
    if kind == "digest" and not LLM_EDITOR_DIGEST_ENABLED:
        return False
    if kind == "breaking" and not LLM_EDITOR_BREAKING_ENABLED:
        return False
    return True


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8") or "null") or default
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _load_stats() -> dict[str, Any]:
    data = _read_json(STATS_FILE, {})
    if not isinstance(data, dict):
        return {}
    data.setdefault("days", {})
    return data


def _day_bucket(stats: dict[str, Any]) -> dict[str, Any]:
    day = _today()
    days = stats.setdefault("days", {})
    bucket = days.setdefault(
        day,
        {
            "requests": 0,
            "prompt_chars": 0,
            "completion_chars": 0,
            "errors": 0,
        },
    )
    stats["current_day"] = day
    return bucket


def _model_uri() -> str:
    model = (YANDEX_LLM_MODEL or "yandexgpt-lite").strip()
    if model.startswith("gpt://"):
        return model
    return f"gpt://{YANDEX_LLM_FOLDER_ID}/{model}/latest"


def _compact_text(value: str, limit: int = LLM_EDITOR_MAX_SUMMARY_CHARS) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "..."


def _json_from_text(text: str) -> Any:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start_candidates = [idx for idx in (cleaned.find("{"), cleaned.find("[")) if idx >= 0]
    if not start_candidates:
        raise ValueError("LLM response does not contain JSON")
    start = min(start_candidates)
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if end <= start:
        raise ValueError("LLM response JSON is incomplete")
    return json.loads(cleaned[start : end + 1])


def _budget_available(kind: str, prompt_chars: int) -> tuple[bool, str]:
    if not llm_editor_enabled(kind):
        return False, "disabled"
    if not (YANDEX_LLM_API_KEY and YANDEX_LLM_FOLDER_ID):
        return False, "not_configured"

    stats = _load_stats()
    bucket = _day_bucket(stats)
    if int(bucket.get("requests", 0)) >= LLM_EDITOR_DAILY_REQUEST_LIMIT:
        return False, "daily_request_limit"
    if int(bucket.get("prompt_chars", 0)) + prompt_chars > LLM_EDITOR_DAILY_CHAR_LIMIT:
        return False, "daily_char_limit"

    if kind == "breaking":
        last_call_at = int(stats.get("last_breaking_call_at", 0) or 0)
        since_last = int(time.time()) - last_call_at
        if last_call_at and since_last < LLM_EDITOR_BREAKING_MIN_INTERVAL_SECONDS:
            return False, "breaking_min_interval"

    return True, "ok"


def _record_call(
    kind: str,
    prompt_chars: int,
    completion_chars: int,
    ok: bool,
    error: str = "",
) -> dict[str, Any]:
    stats = _load_stats()
    bucket = _day_bucket(stats)
    now = int(time.time())

    if ok:
        bucket["requests"] = int(bucket.get("requests", 0)) + 1
        bucket["prompt_chars"] = int(bucket.get("prompt_chars", 0)) + prompt_chars
        bucket["completion_chars"] = int(bucket.get("completion_chars", 0)) + completion_chars
        stats["last_ok_at"] = now
        stats["last_ok_kind"] = kind
        if kind == "breaking":
            stats["last_breaking_call_at"] = now
        if kind == "digest":
            stats["last_digest_call_at"] = now
    else:
        bucket["errors"] = int(bucket.get("errors", 0)) + 1
        stats["last_error_at"] = now
        stats["last_error_kind"] = kind
        stats["last_error"] = error[:300]

    stats["last_prompt_chars"] = prompt_chars
    stats["last_completion_chars"] = completion_chars
    _write_json(STATS_FILE, stats)
    return {
        "daily_requests": int(bucket.get("requests", 0)),
        "daily_prompt_chars": int(bucket.get("prompt_chars", 0)),
        "daily_completion_chars": int(bucket.get("completion_chars", 0)),
        "daily_errors": int(bucket.get("errors", 0)),
    }


def _call_yandex_json(kind: str, system_prompt: str, user_payload: dict[str, Any], max_tokens: int | None = None) -> LLMReviewResult:
    user_text = json.dumps(user_payload, ensure_ascii=False, separators=(",", ":"))
    prompt_chars = len(system_prompt) + len(user_text)
    allowed, reason = _budget_available(kind, prompt_chars)
    if not allowed:
        return LLMReviewResult(False, reason=reason, metrics={"prompt_chars": prompt_chars})

    body = {
        "modelUri": _model_uri(),
        "completionOptions": {
            "stream": False,
            "temperature": YANDEX_LLM_TEMPERATURE,
            "maxTokens": max_tokens or YANDEX_LLM_MAX_TOKENS,
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_text},
        ],
    }

    try:
        response = requests.post(
            YANDEX_LLM_URL,
            headers={
                "Authorization": f"Api-Key {YANDEX_LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=YANDEX_LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        alternatives = ((payload.get("result") or {}).get("alternatives") or [])
        text = ((alternatives[0] or {}).get("message") or {}).get("text") if alternatives else ""
        if not text:
            raise ValueError("empty LLM response")
        parsed = _json_from_text(text)
        metrics = _record_call(kind, prompt_chars, len(text), ok=True)
        metrics.update({"prompt_chars": prompt_chars, "completion_chars": len(text)})
        return LLMReviewResult(True, reason="ok", decisions={}, metrics={"raw": parsed, **metrics})
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        metrics = _record_call(kind, prompt_chars, 0, ok=False, error=error)
        logger.warning("[LLM_EDITOR] %s failed: %s", kind, error)
        return LLMReviewResult(False, reason="error", metrics={"prompt_chars": prompt_chars, "error": error, **metrics})


def review_digest_items(items: list[dict[str, Any]], label: str = "") -> LLMReviewResult:
    if not items:
        return LLMReviewResult(False, reason="empty")

    prepared = []
    for idx, item in enumerate(items[:LLM_EDITOR_MAX_DIGEST_ITEMS], start=1):
        prepared.append(
            {
                "index": idx,
                "title": _compact_text(str(item.get("title", "")), 180),
                "source": _compact_text(str(item.get("source", "")), 80),
                "trust_tier": source_trust_tier(str(item.get("source", ""))),
                "summary": _compact_text(str(item.get("summary", ""))),
                "score": item.get("score"),
                "reason": _compact_text(str(item.get("reason", "")), 160),
            }
        )

    system_prompt = (
        "You are the careful Russian-language editor of a Telegram channel for Real Madrid fans. "
        "Return only valid JSON. Do not add markdown. "
        "Task: keep only items that are clearly relevant to Real Madrid as a football club, "
        "merge your judgement with the provided ranking, and write concise natural Russian headlines. "
        "Reject cricket, basketball, generic World Cup noise, unrelated national-team chatter, "
        "player performance for national teams, old/former-player clickbait, media self-promo, "
        "controversy/drama pieces, and weak rumors. "
        "Reject national-team eliminations, group standings, match reports and player appearances "
        "at the World Cup even if a Real Madrid player is mentioned. Reject Real Madrid basketball. "
        "A story about Mbappe, Vinicius, Valverde, Guler, Bellingham or another Real Madrid player "
        "is not enough: keep it only if it has a direct club consequence such as transfer, contract, "
        "injury, lineup, suspension, official club statement, or Real Madrid matchday impact. "
        "Use names like Real Madrid as «Реал», Jude Bellingham as Джуд Беллингем, "
        "Vinicius as Винисиус, Kylian Mbappe as Килиан Мбаппе. "
        "JSON schema: {\"items\":[{\"index\":1,\"keep\":true,\"headline_ru\":\"...\","
        "\"importance\":0,\"reason\":\"...\"}]}. "
        "headline_ru must be <= 140 characters, no clickbait, no source names, no time."
    )
    result = _call_yandex_json("digest", system_prompt, {"label": label, "items": prepared})
    if not result.used:
        return result

    raw = result.metrics.get("raw")
    rows = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return LLMReviewResult(False, reason="bad_json", metrics=result.metrics)

    decisions: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            index = int(row.get("index"))
        except (TypeError, ValueError):
            continue
        decisions[index] = row

    result.decisions = decisions
    result.metrics.pop("raw", None)
    result.metrics["items_reviewed"] = len(prepared)
    return result


def review_breaking_items(items: list[dict[str, Any]]) -> LLMReviewResult:
    if not items:
        return LLMReviewResult(False, reason="empty")

    prepared = []
    for idx, item in enumerate(items[:LLM_EDITOR_MAX_BREAKING_ITEMS], start=1):
        prepared.append(
            {
                "index": idx,
                "title": _compact_text(str(item.get("title", "")), 180),
                "source": _compact_text(str(item.get("source", "")), 80),
                "trust_tier": source_trust_tier(str(item.get("source", ""))),
                "summary": _compact_text(str(item.get("summary", ""))),
                "fingerprint": _compact_text(str(item.get("fingerprint", "")), 120),
                "first_seen_at": item.get("first_seen_at"),
            }
        )

    system_prompt = (
        "You are the strict duty editor of a Real Madrid Telegram news channel. "
        "Return only valid JSON. Do not add markdown. "
        "Task: decide which candidate deserves an urgent Telegram post. "
        "Post only confirmed or highly important Real Madrid football news: official club statements, "
        "confirmed transfers/departures, serious injuries, lineups, major matchday updates. "
        "Never write 'officially' or 'confirmed' unless the candidate itself is an official source or "
        "explicitly cites an official club statement. A trusted journalist report must be phrased as a report, not as fact. "
        "Reject duplicate variants, generic rumors, unrelated live blogs, cricket, basketball, "
        "generic national-team stories, weak opinion pieces, and clickbait. "
        "If several items describe the same event, keep only the best source. "
        "Write headline_ru in natural Russian, <= 135 characters, no source names, no time. "
        "JSON schema: {\"items\":[{\"index\":1,\"post\":true,\"headline_ru\":\"...\","
        "\"importance\":0,\"reason\":\"...\"}]}. "
        "Use names like «Реал», Винисиус, Джуд Беллингем, Килиан Мбаппе, Дани Себальос."
    )
    result = _call_yandex_json("breaking", system_prompt, {"items": prepared}, max_tokens=min(YANDEX_LLM_MAX_TOKENS, 700))
    if not result.used:
        return result

    raw = result.metrics.get("raw")
    rows = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return LLMReviewResult(False, reason="bad_json", metrics=result.metrics)

    decisions: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            index = int(row.get("index"))
        except (TypeError, ValueError):
            continue
        decisions[index] = row

    result.decisions = decisions
    result.metrics.pop("raw", None)
    result.metrics["items_reviewed"] = len(prepared)
    return result
