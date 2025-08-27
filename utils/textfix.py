import re
from pathlib import Path
import yaml

def _load_yaml_files(paths):
    data = {}
    for p in paths:
        pth = Path(p)
        if not pth.exists():
            continue
        with open(pth, "r", encoding="utf-8") as f:
            chunk = yaml.safe_load(f) or {}
            for k, v in chunk.items():
                if k not in data: data[k] = v
                elif isinstance(v, dict) and isinstance(data[k], dict):
                    data[k].update(v)
                elif isinstance(v, list) and isinstance(data[k], list):
                    data[k].extend(v)
                else:
                    data[k] = v
    return data

def apply_translation_fixes(text: str, rule_files=None) -> str:
    rule_files = rule_files or [
        "data/terms_by_theme.yaml",
        "patches/terms_increment_2025-08-27.yaml",
        "patches/terms_increment_transfers_2025-08-27.yaml",
    ]
    cfg = _load_yaml_files(rule_files)
    fixes = cfg.get("translation_fixes", {})

    for section in ("names_exact","clubs_exact","tournaments_exact","phrases_exact","phrases_ru_cleanup"):
        mapping = fixes.get(section, {}) or {}
        for src, dst in mapping.items():
            text = text.replace(src, dst)

    for rule in fixes.get("regex_rules", []) or []:
        pat = rule.get("pattern"); rep = rule.get("replace","")
        if not pat: continue
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    text = re.sub(r'\"(Реал)\"', r'«\1»', text)
    text = re.sub(r'\s+([,.!?:;])', r'\1', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text
