import yaml
from pathlib import Path
from urllib.parse import urlparse

_MAPPING_CACHE = None

def _load_mapping(paths=None):
    global _MAPPING_CACHE
    if _MAPPING_CACHE is not None:
        return _MAPPING_CACHE
    paths = paths or [
        "patches/source_mapping.yaml",
        "data/source_mapping.yaml",
    ]
    merged = {}
    for p in paths:
        pth = Path(p)
        if not pth.exists():
            continue
        with open(pth, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            merged.update(data.get("source_mapping", {}))
    if "__default__" not in merged:
        merged["__default__"] = "Unknown Source"
    _MAPPING_CACHE = merged
    return _MAPPING_CACHE

def map_source(url: str) -> str:
    mapping = _load_mapping()
    u = urlparse(url)
    base = f"{u.netloc}/"
    path = u.path.strip("/")
    candidates = [
        f"{base}{path}/" if path else f"{base}",
    ]
    if path:
        parts = path.split("/")
        for i in range(1, len(parts)+1):
            prefix = "/".join(parts[:i]) + "/"
            candidates.append(f"{base}{prefix}")
    candidates.append(f"{base}")
    for key in candidates:
        if key in mapping:
            return mapping[key]
    for key in mapping:
        if key == "__default__":
            continue
        if key in (base + path + "/"):
            return mapping[key]
    return mapping.get("__default__", "Unknown Source")
