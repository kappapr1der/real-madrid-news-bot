import json
from datetime import datetime, timezone
from typing import Any

from runtime_config import (
    BREAKING_INTERVAL_SECONDS,
    DRY_RUN,
    HEARTBEAT_BREAKING_STALE_SECONDS,
    HEARTBEAT_LIVE_STALE_SECONDS,
    HEARTBEAT_MAIN_STALE_SECONDS,
    HEARTBEAT_MATCHDAY_STALE_SECONDS,
    LLM_EDITOR_DAILY_CHAR_LIMIT,
    LLM_EDITOR_DAILY_REQUEST_LIMIT,
    LLM_EDITOR_MAX_BREAKING_ITEMS,
    LLM_EDITOR_MAX_DIGEST_ITEMS,
    MATCHDAY_ENABLED,
    MATCHDAY_LIVE_ENABLED,
    PREFLIGHT_STATUS_TTL_SECONDS,
    STATE_DIR,
    STATUS_FILE,
    YANDEX_LLM_ENABLED,
)

STATUS_VERSION = 1
BAD_STATES = {"error", "failed", "restart_limit"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def default_status() -> dict[str, Any]:
    return {
        "version": STATUS_VERSION,
        "updated_at": iso_now(),
        "mode": "dry_run" if DRY_RUN else "live",
        "services": {},
        "last_error": None,
    }


def load_status() -> dict[str, Any]:
    if not STATUS_FILE.exists():
        return default_status()
    try:
        data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_status()
    if not isinstance(data, dict):
        return default_status()
    data.setdefault("version", STATUS_VERSION)
    data.setdefault("updated_at", iso_now())
    data.setdefault("mode", "dry_run" if DRY_RUN else "live")
    data.setdefault("services", {})
    data.setdefault("last_error", None)
    return data


def save_status(status: dict[str, Any]) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATUS_FILE.with_suffix(STATUS_FILE.suffix + ".tmp")
    tmp_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(STATUS_FILE)


def record_status(
    component: str,
    state: str = "ok",
    message: str = "",
    metrics: dict[str, Any] | None = None,
) -> None:
    try:
        status = load_status()
        now = iso_now()
        status["updated_at"] = now
        status["mode"] = "dry_run" if DRY_RUN else "live"
        status.setdefault("services", {})[component] = {
            "state": state,
            "updated_at": now,
            "message": message,
            "metrics": metrics or {},
        }
        if state in BAD_STATES:
            status["last_error"] = {
                "component": component,
                "state": state,
                "message": message,
                "updated_at": now,
            }
        save_status(status)
    except OSError:
        # Status must never crash a posting worker.
        return


def record_error(component: str, message: str, metrics: dict[str, Any] | None = None) -> None:
    record_status(component, state="error", message=message, metrics=metrics)


def expected_services() -> dict[str, int]:
    services = {
        "main": HEARTBEAT_MAIN_STALE_SECONDS,
        "breaking": HEARTBEAT_BREAKING_STALE_SECONDS or max(BREAKING_INTERVAL_SECONDS * 3 + 60, 300),
    }
    if MATCHDAY_ENABLED:
        services["matchday"] = HEARTBEAT_MATCHDAY_STALE_SECONDS
    if MATCHDAY_LIVE_ENABLED:
        services["live"] = HEARTBEAT_LIVE_STALE_SECONDS
    return services


def service_age_seconds(entry: dict[str, Any], now: datetime) -> int | None:
    updated_at = parse_iso(str(entry.get("updated_at") or ""))
    if not updated_at:
        return None
    return int((now - updated_at).total_seconds())


def load_state_json(name: str) -> dict[str, Any]:
    path = STATE_DIR / name
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def recent_day_rows(days: dict[str, Any], limit: int = 7) -> dict[str, Any]:
    if not isinstance(days, dict):
        return {}
    keys = sorted(str(key) for key in days.keys())[-limit:]
    return {key: days.get(key, {}) for key in keys}


def usage_snapshot() -> dict[str, Any]:
    today = utc_now().strftime("%Y-%m-%d")
    llm_stats = load_state_json("llm_editor_stats.json")
    llm_days = llm_stats.get("days", {}) if isinstance(llm_stats.get("days"), dict) else {}
    llm_today = llm_days.get(today, {}) if isinstance(llm_days.get(today), dict) else {}
    prompt_chars = int(llm_today.get("prompt_chars", 0) or 0)
    requests = int(llm_today.get("requests", 0) or 0)

    translation_stats = load_state_json("translation_stats.json")
    translation_days = (
        translation_stats.get("days", {}) if isinstance(translation_stats.get("days"), dict) else {}
    )
    translation_today = (
        translation_days.get(today, {}) if isinstance(translation_days.get(today), dict) else {}
    )

    return {
        "date": today,
        "llm_editor": {
            "enabled": YANDEX_LLM_ENABLED,
            "today": llm_today,
            "last_7_days": recent_day_rows(llm_days),
            "limits": {
                "daily_requests": LLM_EDITOR_DAILY_REQUEST_LIMIT,
                "daily_prompt_chars": LLM_EDITOR_DAILY_CHAR_LIMIT,
                "max_digest_items": LLM_EDITOR_MAX_DIGEST_ITEMS,
                "max_breaking_items": LLM_EDITOR_MAX_BREAKING_ITEMS,
            },
            "utilization": {
                "requests_percent": round(requests * 100 / max(LLM_EDITOR_DAILY_REQUEST_LIMIT, 1), 1),
                "prompt_chars_percent": round(prompt_chars * 100 / max(LLM_EDITOR_DAILY_CHAR_LIMIT, 1), 1),
            },
            "last_ok_at": llm_stats.get("last_ok_at"),
            "last_ok_kind": llm_stats.get("last_ok_kind"),
            "last_error_at": llm_stats.get("last_error_at"),
            "last_error_kind": llm_stats.get("last_error_kind"),
            "last_error": llm_stats.get("last_error"),
        },
        "translation": {
            "today": translation_today,
            "last_7_days": recent_day_rows(translation_days),
            "providers": translation_stats.get("providers", {}),
            "total_events": translation_stats.get("total_events", 0),
            "total_input_chars": translation_stats.get("total_input_chars", 0),
            "last_ok_provider": translation_stats.get("last_ok_provider"),
            "last_ok_at": translation_stats.get("last_ok_at"),
            "last_error_provider": translation_stats.get("last_error_provider"),
            "last_error_at": translation_stats.get("last_error_at"),
        },
    }


def health_snapshot() -> tuple[dict[str, Any], int]:
    status = load_status()
    now = utc_now()
    services = status.get("services", {}) if isinstance(status.get("services"), dict) else {}
    expected = expected_services()
    issues = []
    warnings = []
    usage = usage_snapshot()

    for name, max_age in expected.items():
        entry = services.get(name)
        if not isinstance(entry, dict):
            issues.append(f"{name} has not reported yet")
            continue

        state = str(entry.get("state") or "unknown")
        if state in BAD_STATES:
            issues.append(f"{name} is {state}: {entry.get('message') or ''}".strip())

        age = service_age_seconds(entry, now)
        if age is None:
            issues.append(f"{name} has invalid updated_at")
        elif age > max_age:
            issues.append(f"{name} stale for {age}s, limit {max_age}s")

    for name, entry in services.items():
        if not str(name).startswith("preflight:") or not isinstance(entry, dict):
            continue
        age = service_age_seconds(entry, now)
        if age is None or age > PREFLIGHT_STATUS_TTL_SECONDS:
            continue
        state = str(entry.get("state") or "unknown")
        message = str(entry.get("message") or "").strip()
        if state in BAD_STATES:
            issues.append(f"{name} is {state}: {message}".strip())
        elif state == "degraded":
            warnings.append(f"{name}: {message}".strip())

    llm_utilization = usage.get("llm_editor", {}).get("utilization", {})
    if float(llm_utilization.get("requests_percent", 0) or 0) >= 90:
        warnings.append("LLM editor daily request limit is above 90%")
    if float(llm_utilization.get("prompt_chars_percent", 0) or 0) >= 90:
        warnings.append("LLM editor daily prompt char limit is above 90%")

    payload = {
        "ok": not issues,
        "checked_at": now.isoformat(),
        "mode": "dry_run" if DRY_RUN else "live",
        "issues": issues,
        "warnings": warnings,
        "expected_services": expected,
        "usage": usage,
        "status": status,
    }
    return payload, 200 if not issues else 503
