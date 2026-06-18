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
    MATCHDAY_ENABLED,
    MATCHDAY_LIVE_ENABLED,
    STATUS_FILE,
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


def health_snapshot() -> tuple[dict[str, Any], int]:
    status = load_status()
    now = utc_now()
    services = status.get("services", {}) if isinstance(status.get("services"), dict) else {}
    expected = expected_services()
    issues = []

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

    payload = {
        "ok": not issues,
        "checked_at": now.isoformat(),
        "mode": "dry_run" if DRY_RUN else "live",
        "issues": issues,
        "expected_services": expected,
        "status": status,
    }
    return payload, 200 if not issues else 503
