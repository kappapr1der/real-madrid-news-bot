import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from runtime_config import STORY_LIFECYCLE_ENABLED, get_state_file
from transfer_tracker import STATUS_WEIGHT, classify_status, extract_subject, is_transfer_story


LIFECYCLE_FILE = get_state_file("story_lifecycle.json")
INJURY_TERMS = ("injury", "injured", "lesion", "травм", "поврежден")
RETURN_TERMS = ("returns", "return", "back in training", "available", "recovers", "вернулся", "восстанов", "готов к")
CONTRACT_TERMS = ("renewal", "extends", "extension", "contract", "renueva", "contrato", "продлен", "продлил", "контракт")
CONTRACT_DONE_TERMS = ("official", "oficial", "confirmed", "confirmado", "announces", "announce", "подписал", "объявил", "продлил")
CONTRACT_DENIAL_TERMS = ("denies", "denied", "no agreement", "not negotiating", "desmiente", "descarta", "опроверг", "не ведет переговор")


@dataclass(frozen=True)
class LifecycleDecision:
    relevant: bool
    changed: bool
    key: str = ""
    status: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    if not LIFECYCLE_FILE.exists():
        return {"version": 1, "entries": {}}
    try:
        data = json.loads(LIFECYCLE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "entries": {}}
    if not isinstance(data, dict):
        return {"version": 1, "entries": {}}
    data["version"] = 1
    data["entries"] = data.get("entries") if isinstance(data.get("entries"), dict) else {}
    return data


def _save(data: dict) -> None:
    LIFECYCLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{LIFECYCLE_FILE.name}.",
        suffix=".tmp",
        dir=LIFECYCLE_FILE.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, LIFECYCLE_FILE)
    finally:
        tmp_path.unlink(missing_ok=True)


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def _injury_status(text: str) -> str:
    return "return" if any(term in text for term in RETURN_TERMS) else "injury"


def _contract_status(text: str) -> str:
    if any(term in text for term in CONTRACT_DENIAL_TERMS):
        return "denied"
    if any(term in text for term in CONTRACT_DONE_TERMS):
        return "completed"
    return "talks"


def classify_lifecycle(title: str, source: str = "", category: str = "", fingerprint: str = "") -> tuple[str, str, str]:
    subject = extract_subject(title)
    if not subject:
        return "", "", ""
    text = _normal(" ".join((title, category, fingerprint)))
    if is_transfer_story(title, category, fingerprint):
        return "transfer", subject, classify_status(title, source)
    if any(term in text for term in INJURY_TERMS):
        return "injury", subject, _injury_status(text)
    if any(term in text for term in CONTRACT_TERMS):
        return "contract", subject, _contract_status(text)
    return "", "", ""


def lifecycle_decision(title: str, source: str = "", category: str = "", fingerprint: str = "") -> LifecycleDecision:
    if not STORY_LIFECYCLE_ENABLED:
        return LifecycleDecision(False, True)
    family, subject, status = classify_lifecycle(title, source, category, fingerprint)
    if not family:
        return LifecycleDecision(False, True)
    key = f"{family}:{subject.casefold()}"
    current = _load()["entries"].get(key) or {}
    previous_status = str(current.get("status") or "")
    if (
        family == "transfer"
        and previous_status in STATUS_WEIGHT
        and status in STATUS_WEIGHT
        and STATUS_WEIGHT[previous_status] > STATUS_WEIGHT[status]
        and status != "опровергнуто"
    ):
        status = previous_status
    return LifecycleDecision(True, previous_status != status, key, status)


def record_lifecycle(title: str, source: str = "", link: str = "", category: str = "", fingerprint: str = "") -> LifecycleDecision:
    decision = lifecycle_decision(title, source, category, fingerprint)
    if not decision.relevant:
        return decision
    data = _load()
    entries = data["entries"]
    row = entries.setdefault(decision.key, {"history": []})
    now = _now()
    changed = row.get("status") != decision.status
    row.update({"status": decision.status, "title": title, "source": source, "link": link, "last_seen_at": now})
    if changed:
        row.setdefault("history", []).append({"status": decision.status, "title": title, "source": source, "link": link, "at": now})
        row["history"] = row["history"][-20:]
        row["updated_at"] = now
    _save(data)
    return LifecycleDecision(True, changed, decision.key, decision.status)


def lifecycle_summary() -> dict[str, int]:
    entries = _load()["entries"]
    return {
        "tracked": len(entries),
        "transfers": sum(1 for key in entries if str(key).startswith("transfer:")),
        "injuries": sum(1 for key in entries if str(key).startswith("injury:")),
        "contracts": sum(1 for key in entries if str(key).startswith("contract:")),
    }
