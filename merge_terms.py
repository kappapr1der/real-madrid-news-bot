#!/usr/bin/env python3
"""
Merge additions.yaml into terms_by_theme.yaml.

- Deep-merges dictionaries (additions override/extend base).
- If a value is a list, it appends only new items (сохраняет порядок и уникальность).
- Creates a timestamped backup of the original terms_by_theme.yaml.
- Prints a short diff summary: added/updated keys per top-level section.
- Supports --dry-run (ничего не записывает) и --output <path> (писать в другой файл).

Usage:
  python merge_terms.py
  python merge_terms.py --dry-run
  python merge_terms.py --base path/to/terms_by_theme.yaml --add path/to/additions.yaml
  python merge_terms.py --output merged.yaml
"""

import argparse
import copy
import datetime as dt
import os
import sys
from typing import Any, Dict, List, Tuple

try:
    import yaml  # PyYAML
except ImportError as e:
    print("ERROR: PyYAML не установлен. Установите: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

DEFAULT_BASE = "terms_by_theme.yaml"
DEFAULT_ADD  = "additions.yaml"

def deep_merge(base: Any, add: Any) -> Any:
    """Deep-merge add into base with the following rules:
    - dict: recursively merge, additions override/extend.
    - list: append only elements not present in base (preserve order).
    - scalar: addition replaces base.
    """
    if base is None:
        return copy.deepcopy(add)
    if add is None:
        return base

    if isinstance(base, dict) and isinstance(add, dict):
        result = dict(base)
        for k, v in add.items():
            if k in result:
                result[k] = deep_merge(result[k], v)
            else:
                result[k] = copy.deepcopy(v)
        return result

    if isinstance(base, list) and isinstance(add, list):
        result = list(base)
        seen = set(base)
        for item in add:
            if item not in seen:
                result.append(item)
                seen.add(item)
        return result

    # Different types or scalar: prefer 'add'
    return copy.deepcopy(add)

def diff_sections(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """
    Return a summary per top-level section:
      {'names': {'added': X, 'updated': Y}, ...}
    Only meaningful for mapping sections.
    """
    summary: Dict[str, Dict[str, int]] = {}
    for section, after_val in after.items():
        if not isinstance(after_val, dict):
            continue
        before_val = before.get(section, {})
        if not isinstance(before_val, dict):
            added = len(after_val)
            summary[section] = {"added": added, "updated": 0}
            continue

        added = 0
        updated = 0
        for k, v in after_val.items():
            if k not in before_val:
                added += 1
            else:
                if before_val[k] != v:
                    updated += 1
        if added or updated:
            summary[section] = {"added": added, "updated": updated}
    return summary

def load_yaml(path: str) -> Any:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def dump_yaml(data: Any, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            data, f, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=False
        )

def make_backup(path: str) -> str:
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{path}.bak.{ts}"
    with open(path, "rb") as src, open(backup_path, "wb") as dst:
        dst.write(src.read())
    return backup_path

def main():
    ap = argparse.ArgumentParser(description="Merge additions.yaml into terms_by_theme.yaml")
    ap.add_argument("--base", default=DEFAULT_BASE, help="Path to base terms YAML (default: terms_by_theme.yaml)")
    ap.add_argument("--add",  default=DEFAULT_ADD,  help="Path to additions YAML (default: additions.yaml)")
    ap.add_argument("--output", default=None, help="Write merged YAML to this path (default: overwrite base)")
    ap.add_argument("--dry-run", action="store_true", help="Do not write files, only show summary")
    args = ap.parse_args()

    base_path = args.base
    add_path  = args.add
    out_path  = args.output or base_path

    base = load_yaml(base_path)
    additions = load_yaml(add_path)

    if not additions:
        print(f"Nothing to merge: {add_path} пуст или не найден.", file=sys.stderr)
        sys.exit(2)

    merged = deep_merge(base, additions)
    summary = diff_sections(base if isinstance(base, dict) else {}, merged if isinstance(merged, dict) else {})

    if args.dry_run:
        print("[DRY-RUN] Merge summary:")
        if not summary:
            print("  No changes detected.")
        else:
            for sec, cnts in summary.items():
                print(f"  {sec}: +{cnts.get('added',0)} added, {cnts.get('updated',0)} updated")
        print("\nNo files were written.")
        return

    # Create backup if overwriting the base file
    if out_path == base_path and os.path.exists(base_path):
        backup_path = make_backup(base_path)
        print(f"Backup created: {backup_path}")

    dump_yaml(merged, out_path)
    print(f"Merged YAML written to: {out_path}")

    if summary:
        print("Changes:")
        for sec, cnts in summary.items():
            print(f"  {sec}: +{cnts.get('added',0)} added, {cnts.get('updated',0)} updated")
    else:
        print("No changes detected (files identical).")

if __name__ == "__main__":
    main()
