#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import logging
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from content_quality import rank_digest_candidates
from digest import (
    apply_digest_hard_deny,
    collect_candidates,
    lookback_hours_for_label,
    normalize_label,
    normalized_similarity_threshold,
)
from match_calendar import digest_block_reason
from runtime_config import (
    BREAKING_PREFLIGHT_PENDING_WARN,
    DIGEST_DEDUPE_ENABLED,
    DIGEST_LIMIT,
    DIGEST_PREFLIGHT_WARN_MIN_CANDIDATES,
    DIGEST_PRIORITY_SORT_ENABLED,
    DRY_RUN,
    LLM_EDITOR_BREAKING_BUFFER_SECONDS,
    LLM_EDITOR_BREAKING_FALLBACK_AFTER_SECONDS,
    LLM_EDITOR_MAX_DIGEST_ITEMS,
    get_log_file,
    get_state_file,
)
from sources_international import SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU
from status_manager import record_error, record_status
from text_cleaner import clean_text


LOG_FILE = get_log_file("preflight.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

BREAKING_PENDING_FILE = get_state_file("breaking_llm_pending.json")

LABEL_SLUGS = {
    "утреннего": "morning",
    "дневного": "day",
    "вечернего": "evening",
    "ночного": "night",
    "default": "default",
}


def label_slug(label: str) -> str:
    return LABEL_SLUGS.get(label, "default")


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "[]")
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def breaking_queue_snapshot() -> dict[str, Any]:
    rows = load_json_rows(BREAKING_PENDING_FILE)
    now = int(time.time())
    ages = [max(now - int(row.get("first_seen_at", now) or now), 0) for row in rows]
    ready = [age for age in ages if age >= LLM_EDITOR_BREAKING_BUFFER_SECONDS]
    stale = [age for age in ages if age >= LLM_EDITOR_BREAKING_FALLBACK_AFTER_SECONDS]
    source_counts = Counter(str(row.get("source") or "unknown") for row in rows)
    preview = [
        {
            "title": clean_text(str(row.get("title") or "")),
            "source": str(row.get("source") or "unknown"),
            "age_seconds": age,
            "seen_count": int(row.get("seen_count", 1) or 1),
        }
        for row, age in sorted(zip(rows, ages), key=lambda pair: pair[1], reverse=True)[:5]
    ]
    return {
        "pending": len(rows),
        "ready": len(ready),
        "stale": len(stale),
        "oldest_age_seconds": max(ages) if ages else 0,
        "sources": dict(source_counts.most_common(5)),
        "preview": preview,
    }


def digest_preflight(label: str) -> dict[str, Any]:
    normalized = normalize_label(label)
    component = f"preflight:digest:{label_slug(normalized)}"
    record_status(component, "starting", "digest preflight started", {"label": normalized})

    block_reason = digest_block_reason()
    if block_reason:
        metrics = {"label": normalized, "reason": block_reason}
        record_status(component, "skipped", block_reason, metrics)
        return metrics

    lookback_hours = lookback_hours_for_label(normalized)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    sources = SOURCES_INTERNATIONAL + SOURCES_RU
    candidates = collect_candidates(sources, cutoff)
    review_limit = max(DIGEST_LIMIT, LLM_EDITOR_MAX_DIGEST_ITEMS)
    ranked = rank_digest_candidates(
        candidates,
        limit=review_limit,
        dedupe_enabled=DIGEST_DEDUPE_ENABLED,
        priority_sort_enabled=DIGEST_PRIORITY_SORT_ENABLED,
        similarity_threshold=normalized_similarity_threshold(),
    )
    filtered, hard_dropped = apply_digest_hard_deny(ranked)
    selected = filtered[:DIGEST_LIMIT]
    grouped_links = sum(max(len(item.grouped_links) - 1, 0) for item in selected)
    source_counts = Counter(str(item.candidate.source or "unknown") for item in selected)
    category_counts = Counter(item.category or "general" for item in selected)
    preview = [
        {
            "title": clean_text(str(item.candidate.title or "")),
            "source": str(item.candidate.source or "unknown"),
            "score": item.score,
            "category": item.category,
            "grouped_links": len(item.grouped_links),
            "related_sources": item.related_sources[:3],
        }
        for item in selected[:5]
    ]
    breaking_queue = breaking_queue_snapshot()

    warnings: list[str] = []
    if not candidates:
        warnings.append("no digest candidates found")
    if not selected:
        warnings.append("no digest items selected after filters")
    elif len(selected) < DIGEST_PREFLIGHT_WARN_MIN_CANDIDATES:
        warnings.append(f"thin digest: selected {len(selected)} items")
    if breaking_queue["pending"] >= BREAKING_PREFLIGHT_PENDING_WARN:
        warnings.append(f"breaking queue pending {breaking_queue['pending']} items")
    if breaking_queue["stale"]:
        warnings.append(f"breaking queue has {breaking_queue['stale']} stale items")

    metrics = {
        "label": normalized,
        "lookback_hours": lookback_hours,
        "sources": len(sources),
        "candidates": len(candidates),
        "ranked": len(ranked),
        "selected": len(selected),
        "grouped_links": grouped_links,
        "hard_dropped": hard_dropped,
        "dedupe": DIGEST_DEDUPE_ENABLED,
        "priority_sort": DIGEST_PRIORITY_SORT_ENABLED,
        "source_counts": dict(source_counts.most_common(5)),
        "category_counts": dict(category_counts),
        "preview": preview,
        "breaking_queue": breaking_queue,
        "warnings": warnings,
        "dry_run": DRY_RUN,
    }
    state = "degraded" if warnings else "ok"
    message = "; ".join(warnings) if warnings else f"{normalized} digest preflight ok"
    record_status(component, state, message, metrics)
    logging.info(
        "Preflight label=%s candidates=%s selected=%s grouped=%s hard_dropped=%s warnings=%s",
        normalized,
        len(candidates),
        len(selected),
        grouped_links,
        hard_dropped,
        len(warnings),
    )
    return metrics


def run_digest_preflight(label: str) -> int:
    try:
        metrics = digest_preflight(label)
    except Exception as exc:
        record_error("preflight:digest", f"digest preflight failed: {exc}")
        logging.exception("Digest preflight failed")
        print(f"[PREFLIGHT] digest failed: {exc}")
        return 1

    print(
        "[PREFLIGHT] {label}: candidates={candidates}, selected={selected}, warnings={warnings}".format(
            label=metrics.get("label"),
            candidates=metrics.get("candidates"),
            selected=metrics.get("selected"),
            warnings=len(metrics.get("warnings", [])),
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Coffee Bot lightweight preflight checks")
    subparsers = parser.add_subparsers(dest="command")

    digest_parser = subparsers.add_parser("digest", help="check a digest slot without posting")
    digest_parser.add_argument("label", nargs="?", default="auto")

    subparsers.add_parser("breaking", help="record breaking queue health only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "breaking":
        metrics = {"breaking_queue": breaking_queue_snapshot(), "dry_run": DRY_RUN}
        warnings = []
        if metrics["breaking_queue"]["pending"] >= BREAKING_PREFLIGHT_PENDING_WARN:
            warnings.append(f"breaking queue pending {metrics['breaking_queue']['pending']} items")
        if metrics["breaking_queue"]["stale"]:
            warnings.append(f"breaking queue has {metrics['breaking_queue']['stale']} stale items")
        metrics["warnings"] = warnings
        record_status("preflight:breaking", "degraded" if warnings else "ok", "; ".join(warnings) or "breaking preflight ok", metrics)
        print(f"[PREFLIGHT] breaking: pending={metrics['breaking_queue']['pending']}, warnings={len(warnings)}")
        return 0

    return run_digest_preflight(getattr(args, "label", "auto"))


if __name__ == "__main__":
    raise SystemExit(main())
