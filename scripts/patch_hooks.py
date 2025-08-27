#!/usr/bin/env python3
import re, shutil
from pathlib import Path

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
        s = re.sub(
            r"(^\s*(?:import|from)\b[^\n]*\n(?:^\s*(?:import|from)\b[^\n]*\n)*)",
            r"\1from utils.textfix import apply_translation_fixes\n",
            s, count=1, flags=re.M
        )
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
            s, count=1
        )
        print("[ok ] translator: добавлен вызов apply_translation_fixes")
    else:
        print("[ok ] translator: вызов уже есть")

    p.write_text(s, encoding="utf-8")

def ensure_helpers_in_digest(s: str) -> str:
    # Импорты
    if "from utils.source_map import map_source" not in s:
        s = re.sub(
            r"(^\s*(?:import|from)\b[^\n]*\n(?:^\s*(?:import|from)\b[^\n]*\n)*)",
            r"\1from utils.source_map import map_source\nfrom utils.time_labels import digest_label\nfrom utils.title_extractor import extract_title\n",
            s, count=1, flags=re.M
        )

    # Хелперы
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

    # Замена _format_entry при помощи функции-заменителя (не строка!)
    pattern = r"def\s+_format_entry\([^\)]*\):[\s\S]*?(?=\n\n|\Z)"
    repl_code = (
        "def _format_entry(idx, item):\n"
        "    title = _safe_title(item).replace('\"Реал\"', '«Реал»')\n"
        "    url = item['url']\n"
        "    source = _safe_source(item)\n"
        "    return f\"{idx}\\uFE0F\\u20E3 {title}\\n🔗 {url}\\nИсточник: {source}\""
    )
    if re.search(pattern, s):
        s = re.sub(pattern, lambda m: repl_code, s, count=1)
    else:
        # если у тебя нет _format_entry — просто добавим в конец
        s += "\n\n" + repl_code + "\n"

    # Заголовок дайджеста по времени
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
    # просто пытаемся пропатчить оба файла
    for name in FILES:
        p = Path(name)
        if not p.exists():
            print(f"[skip] {name} не найден — пропускаю")
            continue
        if p.name == "translator.py":
            patch_translator(p)
        elif p.name == "digest.py":
            patch_digest(p)
    print("✓ done")

if __name__ == "__main__":
    main()
