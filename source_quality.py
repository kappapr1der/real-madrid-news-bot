import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from runtime_config import (
    SOURCE_QUALITY_AUTOPILOT_ENABLED,
    SOURCE_QUALITY_BACKUP_MIN_CANDIDATES,
    SOURCE_QUALITY_BACKUP_QUARANTINE_RATE,
    SOURCE_QUALITY_HARD_BLOCK_ENABLED,
    SOURCE_QUALITY_HARD_BLOCK_MIN_CANDIDATES,
    SOURCE_QUALITY_HARD_BLOCK_QUARANTINE_RATE,
    get_state_file,
)
from status_manager import record_status

SOURCE_QUALITY_FILE = get_state_file("source_quality.json")
MAX_WATCHLIST = 8
MIN_QUALITY_SAMPLE = 12

SOURCE_TIER_RULES = (
    (
        "official",
        (
            "realmadrid.com",
            "x - @realmadrid",
            "x - @realmadriden",
        ),
    ),
    (
        "reporter",
        (
            "x - @mariocortegana",
            "x - @aranchamobile",
            "x - @melchorcope",
            "x - @jlsanchez78",
            "x - @ramon_alvarezmm",
            "x - @guillermorai_",
            "x - @fabrizioromano",
            "fabrizio romano - telegram",
        ),
    ),
    (
        "established_media",
        (
            "marca",
            "mundo deportivo",
            "sport - real madrid",
            "bbc sport",
            "guardian football",
            "espn fc",
            "sky sports",
            "ny times",
        ),
    ),
    (
        "specialized_media",
        (
            "managing madrid",
            "madrid universal",
            "bernabeu digital",
            "defensa central",
            "football españa",
            "football espana",
            "real madrid news",
            "the real champs",
        ),
    ),
)


def source_label(source: Any) -> str:
    if isinstance(source, dict):
        return str(source.get("label") or source.get("url") or "unknown")
    return str(source or "unknown")


def normalized_source_name(source: Any) -> str:
    return (
        source_label(source)
        .casefold()
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("–", "-")
        .replace("—", "-")
        .strip()
    )


def source_trust_tier(source: Any) -> str:
    normalized = normalized_source_name(source)
    for tier, markers in SOURCE_TIER_RULES:
        if any(marker in normalized for marker in markers):
            return tier
    return "community"


def source_provenance_label(source: Any) -> str:
    tier = source_trust_tier(source)
    if tier == "official":
        return "официальный источник"
    if tier == "reporter":
        return "журналист"
    return ""


def candidate_source(candidate: Any) -> str:
    return str(getattr(candidate, "source", "") or "unknown")


def load_source_quality() -> dict:
    if not SOURCE_QUALITY_FILE.exists():
        return {"version": 1, "sources": {}}
    try:
        data = json.loads(SOURCE_QUALITY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "sources": {}}
    if not isinstance(data, dict):
        return {"version": 1, "sources": {}}
    data.setdefault("version", 1)
    data.setdefault("sources", {})
    return data


def save_source_quality(data: dict) -> None:
    SOURCE_QUALITY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def source_quality_adjustment(source: Any, data: dict | None = None) -> int:
    data = data if isinstance(data, dict) else load_source_quality()
    normalized = normalized_source_name(source)
    row = next(
        (
            value
            for label, value in (data.get("sources") or {}).items()
            if isinstance(value, dict) and normalized_source_name(label) == normalized
        ),
        None,
    )
    if not isinstance(row, dict):
        return 0

    candidates = int(row.get("candidates") or 0)
    if candidates < MIN_QUALITY_SAMPLE:
        return 0
    selected = int(row.get("selected") or 0)
    quarantined = int(row.get("quarantined") or 0)
    selected_rate = selected / candidates
    quarantine_rate = quarantined / candidates

    policy = source_quality_policy(source, data)
    if policy == "blocked":
        return -24
    if policy == "backup":
        return -8
    if quarantine_rate >= 0.45:
        return -4
    if quarantine_rate >= 0.35:
        return -2
    if selected >= 6 and selected_rate >= 0.50:
        return 2
    return 0


def source_quality_policy(source: Any, data: dict | None = None) -> str:
    """Return the current editorial treatment for a source.

    The default is intentionally conservative: trusted official/reporter feeds never
    get automatically blocked, and hard blocking needs an explicit opt-in.
    """
    if not SOURCE_QUALITY_AUTOPILOT_ENABLED:
        return "normal"
    if source_trust_tier(source) in {"official", "reporter"}:
        return "normal"

    data = data if isinstance(data, dict) else load_source_quality()
    normalized = normalized_source_name(source)
    row = next(
        (
            value
            for label, value in (data.get("sources") or {}).items()
            if isinstance(value, dict) and normalized_source_name(label) == normalized
        ),
        None,
    )
    if not isinstance(row, dict):
        return "normal"
    candidates = int(row.get("candidates") or 0)
    selected = int(row.get("selected") or 0)
    quarantined = int(row.get("quarantined") or 0)
    if candidates <= 0:
        return "normal"
    quarantine_rate = quarantined / candidates
    selected_rate = selected / candidates
    if (
        SOURCE_QUALITY_HARD_BLOCK_ENABLED
        and candidates >= SOURCE_QUALITY_HARD_BLOCK_MIN_CANDIDATES
        and quarantine_rate >= SOURCE_QUALITY_HARD_BLOCK_QUARANTINE_RATE
        and selected_rate < 0.20
    ):
        return "blocked"
    if (
        candidates >= SOURCE_QUALITY_BACKUP_MIN_CANDIDATES
        and quarantine_rate >= SOURCE_QUALITY_BACKUP_QUARANTINE_RATE
        and selected_rate < 0.35
    ):
        return "backup"
    return "normal"


def source_snapshot(row: dict) -> dict:
    runs = max(int(row.get("runs") or 0), 1)
    candidates = int(row.get("candidates") or 0)
    selected = int(row.get("selected") or 0)
    quarantined = int(row.get("quarantined") or 0)
    return {
        "source": row.get("label", "unknown"),
        "runs": runs,
        "candidates": candidates,
        "selected": selected,
        "quarantined": quarantined,
        "selected_rate": round(selected / max(candidates, 1), 3),
        "candidate_rate": round(candidates / runs, 2),
        "quarantine_rate": round(quarantined / max(candidates, 1), 3),
        "trust_tier": source_trust_tier(row.get("label", "unknown")),
        "policy": source_quality_policy(row.get("label", "unknown"), {"sources": {row.get("label", "unknown"): row}}),
        "quality_adjustment": source_quality_adjustment(row.get("label", "unknown"), {"sources": {row.get("label", "unknown"): row}}),
    }


def summarize_source_quality(data: dict) -> dict:
    rows = []
    for label, row in data.get("sources", {}).items():
        if not isinstance(row, dict):
            continue
        row.setdefault("label", label)
        rows.append(source_snapshot(row))

    productive = sorted(
        rows,
        key=lambda row: (row["selected"], row["selected_rate"], row["candidates"]),
        reverse=True,
    )[:MAX_WATCHLIST]
    noisy = sorted(
        [row for row in rows if row["candidates"] >= 3],
        key=lambda row: (row["quarantine_rate"], row["candidates"] - row["selected"]),
        reverse=True,
    )[:MAX_WATCHLIST]
    quiet = sorted(
        [row for row in rows if row["runs"] >= 3 and row["candidates"] == 0],
        key=lambda row: row["runs"],
        reverse=True,
    )[:MAX_WATCHLIST]
    return {
        "tracked_sources": len(rows),
        "productive": productive,
        "noisy": noisy,
        "quiet": quiet,
    }


def update_digest_source_quality(
    *,
    sources: list[Any],
    candidates: list[Any],
    selected: list[Any],
    quarantined_by_source: dict[str, int] | None = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    data = load_source_quality()
    rows = data.setdefault("sources", {})

    candidate_counts = Counter(candidate_source(candidate) for candidate in candidates)
    selected_counts = Counter(candidate_source(item.candidate) for item in selected)
    quarantined_counts = Counter(quarantined_by_source or {})

    labels = {source_label(source) for source in sources}
    labels.update(candidate_counts)
    labels.update(selected_counts)
    labels.update(quarantined_counts)

    for label in sorted(labels):
        row = rows.setdefault(
            label,
            {
                "label": label,
                "runs": 0,
                "candidates": 0,
                "selected": 0,
                "quarantined": 0,
            },
        )
        row["label"] = label
        row["runs"] = int(row.get("runs") or 0) + 1
        row["candidates"] = int(row.get("candidates") or 0) + candidate_counts.get(label, 0)
        row["selected"] = int(row.get("selected") or 0) + selected_counts.get(label, 0)
        row["quarantined"] = int(row.get("quarantined") or 0) + quarantined_counts.get(label, 0)
        row["last_seen_at"] = now
        row["last_candidates"] = candidate_counts.get(label, 0)
        row["last_selected"] = selected_counts.get(label, 0)
        row["last_quarantined"] = quarantined_counts.get(label, 0)

    data["updated_at"] = now
    save_source_quality(data)
    summary = summarize_source_quality(data)
    record_status("source_quality", "ok", "source quality stats updated", summary)
    return summary
