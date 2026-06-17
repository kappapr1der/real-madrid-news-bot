import re

HASHTAG_SPLIT_RE = re.compile(r"[\s,]+")
HASHTAG_SAFE_RE = re.compile(r"[^\w]+", re.UNICODE)


def normalize_hashtag(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if value.startswith("#"):
        value = value[1:]
    value = HASHTAG_SAFE_RE.sub("_", value).strip("_")
    if not value:
        return ""
    return f"#{value}"


def format_hashtags(raw: str) -> str:
    seen = set()
    tags: list[str] = []
    for token in HASHTAG_SPLIT_RE.split(raw or ""):
        tag = normalize_hashtag(token)
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        tags.append(tag)
    return " ".join(tags)


def append_hashtags(message: str, raw_hashtags: str) -> str:
    tags = format_hashtags(raw_hashtags)
    if not tags:
        return message
    return f"{message.rstrip()}\n\n{tags}"
