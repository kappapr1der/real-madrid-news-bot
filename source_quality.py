import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from runtime_config import get_state_file
from status_manager import record_status

SOURCE_QUALITY_FILE = get_state_file("source_quality.json")
MAX_WATCHLIST = 8


def source_label(source: Any) -> str:
    if isinstance(source, dict):
        return str(source.get("label") or source.get("url") or "unknown")
    return str(source or "unknown")


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
