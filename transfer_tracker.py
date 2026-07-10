import argparse
import json
import re
from datetime import datetime, timezone
from typing import Any

from runtime_config import TRANSFER_TRACKER_ENABLED, get_state_file
from source_quality import source_trust_tier


TRACKER_FILE = get_state_file("transfer_tracker.json")
STATUS_WEIGHT = {
    "слух": 1,
    "подтвержденный интерес": 2,
    "официально": 3,
    "опровергнуто": 4,
}
PLAYER_ALIASES = {
    "Эдуардо Камавинга": ("camavinga", "камавинга"),
    "Майкл Олисе": ("olise", "олисе", "олайс"),
    "Энцо Фернандес": ("enzo fernandez", "энцо фернандес"),
    "Фран Гарсия": ("fran garcia", "фран гарсия"),
    "Нико Пас": ("nico paz", "нико пас"),
    "Рауль Асенсио": ("raul asencio", "асенсио"),
    "Алессандро Бастони": ("bastoni", "бастони"),
    "Арда Гюлер": ("arda guler", "арда гюлер"),
    "Винисиус": ("vinicius", "винисиус", "вини"),
    "Родриго": ("rodrygo", "родриго"),
    "Феде Вальверде": ("valverde", "вальверде"),
    "Орельен Тчуамени": ("tchouameni", "тчуамени", "чуамени"),
    "Майну": ("kobbie mainoo", "майну"),
    "Аюб Буадди": ("bouaddi", "буадди"),
    "Гилберто Мора": ("gilberto mora", "гильберто мора"),
    "Ян Диоманде": ("diomande", "диоманде"),
    "Альваро Каррерас": ("alvaro carreras", "каррерас"),
    "Мигель Гутьеррес": ("miguel gutierrez", "мигель гутьеррес"),
}
TRANSFER_TERMS = (
    "transfer", "fichaje", "signing", "traspaso", "mercado", "buyback", "loan", "sale",
    "transfers", "переход", "трансфер", "подпиш", "аренд", "выкуп", "продаж", "контракт",
)
DENIAL_TERMS = (
    "denies", "denied", "not negotiating", "no plans", "will not sign", "descarta", "desmiente",
    "no fichara", "no fichará", "не подпишет", "опроверга", "не ведет переговор", "не ведёт переговор",
)
OFFICIAL_TERMS = ("official", "oficial", "confirmed", "confirmado", "comunicado", "announces", "announce", "офиц", "объявил", "объявляет")
STRONG_INTEREST_TERMS = (
    "negotiat", "agreement", "agreed", "contacts", "offer", "bid", "talks", "reported by",
    "переговор", "согласовал", "соглашени", "контакт", "предложени",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not TRACKER_FILE.exists():
        return {"version": 1, "entries": {}}
    try:
        data = json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "entries": {}}
    if not isinstance(data, dict):
        return {"version": 1, "entries": {}}
    data["version"] = 1
    data["entries"] = data.get("entries") if isinstance(data.get("entries"), dict) else {}
    return data


def _save(data: dict[str, Any]) -> None:
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold()).strip()


def extract_subject(title: str) -> str:
    text = _normalize(title)
    for subject, aliases in PLAYER_ALIASES.items():
        if any(alias in text for alias in aliases):
            return subject
    return ""


def is_transfer_story(title: str, category: str = "", fingerprint: str = "") -> bool:
    text = _normalize(" ".join((title, category, fingerprint)))
    return text.startswith("transfer:") or any(term in text for term in TRANSFER_TERMS)


def classify_status(title: str, source: str) -> str:
    text = _normalize(title)
    tier = source_trust_tier(source)
    if any(term in text for term in DENIAL_TERMS):
        return "опровергнуто"
    official = any(term in text for term in OFFICIAL_TERMS)
    if official and tier == "official":
        return "официально"
    if tier in {"official", "reporter", "established_media"} and (
        official or any(term in text for term in STRONG_INTEREST_TERMS)
    ):
        return "подтвержденный интерес"
    return "слух"


def record_transfer_story(story: dict[str, Any]) -> dict[str, Any] | None:
    if not TRANSFER_TRACKER_ENABLED:
        return None
    title = str(story.get("title") or "")
    category = str(story.get("category") or "")
    fingerprint = str(story.get("id") or "")
    if not is_transfer_story(title, category, fingerprint):
        return None
    subject = extract_subject(title)
    if not subject:
        return None

    source = str(story.get("source") or "")
    status = classify_status(title, source)
    data = _load()
    entries = data["entries"]
    current = entries.get(subject)
    now = _now()
    update = current is None or current.get("status") != status
    if current is None:
        current = {"subject": subject, "history": []}
        entries[subject] = current

    current["status"] = status
    current["title"] = title
    current["link"] = str(story.get("link") or "")
    current["source"] = source
    current["last_seen_at"] = now
    current["sources"] = list(dict.fromkeys([*(current.get("sources") or []), *list(story.get("sources") or [])]))[-8:]
    if update:
        current.setdefault("history", []).append(
            {"status": status, "title": title, "source": source, "link": current["link"], "at": now}
        )
        current["history"] = current["history"][-20:]
        current["updated_at"] = now
    _save(data)
    return {"subject": subject, "status": status, "changed": update, "updated_at": current.get("updated_at", now)}


def recent_updates(days: int = 7, limit: int = 6) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc).timestamp() - max(days, 1) * 86400
    rows = []
    for entry in _load().get("entries", {}).values():
        if not isinstance(entry, dict):
            continue
        raw = str(entry.get("updated_at") or entry.get("last_seen_at") or "")
        try:
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if stamp >= cutoff:
            rows.append(entry)
    return sorted(rows, key=lambda row: str(row.get("updated_at") or row.get("last_seen_at") or ""), reverse=True)[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Coffee Bot transfer tracker")
    parser.add_argument("--summary", action="store_true", help="print recent tracked transfer state changes")
    args = parser.parse_args()
    if args.summary:
        for row in recent_updates():
            print(f"{row.get('subject')} | {row.get('status')} | {row.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
