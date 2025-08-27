#!/usr/bin/env python3
import re, sys, shutil, os
from pathlib import Path

ROOT = Path(".")
FILES = ["translator.py", "digest.py"]

def backup(p: Path):
    if not p.exists(): 
        print(f"[skip] {p} not found")
        return False
    b = p.with_suffix(p.suffix + ".bak")
    if not b.exists():
        shutil.copy2(p, b)
        print(f"[bak ] {p} -> {b}")
    else:
        print(f"[bak ] {b} already exists")
    return True

def patch_translator(p: Path):
    if not backup(p): return
    s = p.read_text(encoding="utf-8")

    # 1) импорт постпроцессора
    if "from utils.textfix import apply_translation_fixes" not in s:
        # вставим после первого import-блока
        s = re.sub(r"(^\s*import[^\n]*\n(?:^\s*from[^\n]*\n|\s*import[^\n]*\n)*)",
                   r"\1from utils.textfix import apply_translation_fixes\n",
                   s, count=1, flags=re.M)
        print("[ok ] translator: добавлен импорт apply_translation_fixes")
    else:
        print("[ok ] translator: импорт уже есть")

    # 2) хук после перевода
    if "apply_translation_fixes(ru_text)" not in s:
        s = re.sub(
            r"(ru_text\s*=\s*translator\.translate\([^)]+\)\s*)\n",
            r"\1\n"
            r"    try:\n"
            r"        ru_text = apply_translation_fixes(ru_text)\n"
            r"    except Exception as e:\n"
            r"        print(f\"[translator] apply_translation_fixes failed: {e}\")\n\n",
            s, count=1)
        print("[ok ] translator: добавлен вызов apply_translation_fixes")
    else:
        print("[ok ] translator: вызов уже есть")

    p.write_text(s, encoding="utf-8")

def ensure_helpers_in_digest(s: str) -> str:
    # добавим импорты при отсутствии
    if "from utils.source_map import map_source" not in s:
        s = re.sub(r"(^\s*import[^\n]*\n(?:^\s*from[^\n]*\n|\s*import[^\n]*\n)*)",
                   r"\1from utils.source_map import map_source\nfrom utils.time_labels import digest_label\nfrom utils.title_extractor import extract_title\n",
                   s, count=1, flags=re.M)

    # хелперы _safe_title/_safe_source и форматтер
    if "_safe_title(" not in s:
        s += (
            "\n\ndef _safe_title(item) -> str:\n"
            "    t = (item.get('title') or '').strip()\n"
            "    if not t:\n"
            "        fetched = extract_title(item['url'])\n"
            "        if fetched:\n"
            "            t = fetched\n"
            "    return t or 'Без заголовка'\n"
        )
    if "_safe_source(" not in s:
        s += (
            "\n\ndef _safe_source(item) -> str:\n"
            "    s = (item.get('source') or '').strip()\n"
            "    return s or map_source(item['url'])\n"
        )
    # заменим _format_entry на наш вариант
    s = re.sub(
        r"def\s+_format_entry\([^\)]*\):[\s\S]*?(?=\n\n|\Z)",
        "def _format_entry(idx, item):\n"
        "    title = _safe_title(item).replace('\"Реал\"', '«Реал»')\n"
        "    url = item['url']\n"
        "    source = _safe_source(item)\n"
        "    return f\"{idx}\\uFE0F\\u20E3 {title}\\n🔗 {url}\\nИсточник: {source}\"",
        s, count=1
    )

    # заголовок дайджеста — на digest_label()
    s = re.sub(
        r'header\s*=\s*"(?:Вечерние|Дневные|Утренние|Ночные)[^"]*"',
        "header = digest_label()",
        s
    )
    return s

def patch_digest(p: Path):
    if not backup(p): return
    s = p.read_text(encoding="utf-8")
    s2 = ensure_helpers_in_digest(s)
    if s2 != s:
        p.write_text(s2, encoding="utf-8")
        print("[ok ] digest: импорты/хелперы/заголовок обновлены")
    else:
        print("[ok ] digest: изменений не требовалось")

def main():
    # быстрые проверки наличия утилит (чтобы не было ImportError)
    must = [
        "utils/source_map.py", "utils/time_labels.py",
        "utils/title_extractor.py", "utils/textfix.py",
        "patches/source_mapping.yaml",
        "patches/terms_increment_2025-08-27.yaml",
        "patches/terms_increment_transfers_2025-08-27.yaml",
    ]
    missing = [m for m in must if not Path(m).exists()]
    if missing:
        print("[warn] отсутствуют файлы:", ", ".join(missing))
        print("       Сначала запусти мой предыдущий «пакет» с mkdir -p utils patches ...")
    for f in FILES:
        p = Path(f)
        if not p.exists():
            print(f"[skip] {f} не найден — пропускаю")
            continue
        if p.name == "translator.py":
            patch_translator(p)
        elif p.name == "digest.py":
            patch_digest(p)
    print("✓ done")

if __name__ == "__main__":
    main()
