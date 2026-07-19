import json
from datetime import datetime, timezone
from typing import Any

from news_fingerprint import semantic_news_key
from runtime_config import get_state_file


ARCHIVE_FILE = get_state_file("editorial_archive.json")
ARCHIVE_LIMIT = 1500


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not ARCHIVE_FILE.exists():
        return {"version": 1, "stories": []}
    try:
        data = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "stories": []}
    if not isinstance(data, dict):
        return {"version": 1, "stories": []}
    stories = data.get("stories")
    data["stories"] = stories if isinstance(stories, list) else []
    data["version"] = 1
    return data


def _save(data: dict[str, Any]) -> None:
    ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["stories"] = list(data.get("stories") or [])[-ARCHIVE_LIMIT:]
    ARCHIVE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _published_at(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value or _now())


def record_story(
    *,
    kind: str,
    title: str,
    source: str = "",
    link: str = "",
    fingerprint: str = "",
    category: str = "",
    published_at: Any = None,
    related_sources: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one editorial storyline and merge later variants into it."""
    clean_title = str(title or "").strip()
    clean_source = str(source or "").strip()
    clean_link = str(link or "").strip()
    key = str(fingerprint or semantic_news_key(clean_title)).strip()
    if not key:
        key = clean_link or clean_title

    data = _load()
    stories = data["stories"]
    now = _now()
    existing = next((row for row in stories if isinstance(row, dict) and row.get("id") == key), None)
    sources = [clean_source, *(related_sources or [])]
    sources = [value for value in dict.fromkeys(value.strip() for value in sources if value and value.strip())]

    if existing is None:
        existing = {
            "id": key,
            "title": clean_title,
            "link": clean_link,
            "source": clean_source,
            "sources": sources,
            "kinds": [kind],
            "category": category,
            "published_at": _published_at(published_at),
            "first_archived_at": now,
            "last_archived_at": now,
            "metadata": metadata or {},
        }
        stories.append(existing)
    else:
        existing["last_archived_at"] = now
        existing["title"] = clean_title or existing.get("title", "")
        existing["link"] = clean_link or existing.get("link", "")
        existing["source"] = clean_source or existing.get("source", "")
        existing["category"] = category or existing.get("category", "")
        existing["sources"] = list(
            dict.fromkeys([*(existing.get("sources") or []), *sources])
        )
        existing["kinds"] = list(dict.fromkeys([*(existing.get("kinds") or []), kind]))
        if metadata:
            existing["metadata"] = {**(existing.get("metadata") or {}), **metadata}

    _save(data)
    try:
        from transfer_tracker import record_transfer_story

        existing["transfer_update"] = record_transfer_story(existing)
    except Exception:
        # Publication must never fail because a secondary editorial index is unavailable.
        existing["transfer_update"] = None
    return existing


def recent_stories(days: int = 7, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    cutoff = now.astimezone(timezone.utc).timestamp() - max(days, 1) * 86400
    rows: list[dict[str, Any]] = []
    for story in _load().get("stories", []):
        if not isinstance(story, dict):
            continue
        raw = story.get("last_archived_at") or story.get("published_at")
        try:
            stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if stamp >= cutoff:
            rows.append(story)
    return sorted(rows, key=lambda row: str(row.get("last_archived_at") or ""), reverse=True)


def archive_digest_items(label: str, items: list[Any], title_overrides: dict[str, str] | None = None) -> list[dict[str, Any]]:
    title_overrides = title_overrides or {}
    archived = []
    for item in items:
        candidate = getattr(item, "candidate", item)
        raw_title = str(getattr(candidate, "title", "") or "")
        title = title_overrides.get(str(getattr(candidate, "link", "") or ""), raw_title)
        archived.append(
            record_story(
                kind="digest",
                title=title,
                source=str(getattr(candidate, "source", "") or ""),
                link=str(getattr(candidate, "link", "") or ""),
                fingerprint=semantic_news_key(raw_title, str(getattr(candidate, "summary", "") or "")),
                category=str(getattr(item, "category", "") or ""),
                published_at=getattr(candidate, "published_at", None),
                related_sources=list(getattr(item, "related_sources", []) or []),
                metadata={
                    "digest_label": label,
                    "score": getattr(item, "score", None),
                    # Weekly recap can re-translate the original instead of inheriting
                    # a stale or imperfect one-line digest rewrite.
                    "raw_title": raw_title,
                },
            )
        )
    return archived


def archive_matchday_story(match: Any, phase: str, text: str = "", score: str = "") -> dict[str, Any]:
    match_id = str(getattr(match, "id", "match") or "match")
    title = f"{getattr(match, 'title', 'Real Madrid')} - {phase}"
    return record_story(
        kind="matchday",
        title=title,
        source="Match Center",
        fingerprint=f"match:{match_id}:{phase}:{score or 'none'}",
        category="matchday",
        published_at=getattr(match, "kickoff", None),
        metadata={"phase": phase, "text": text[:500], "score": score},
    )
