import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml
from deep_translator import GoogleTranslator, MyMemoryTranslator

logger = logging.getLogger(__name__)

# --- Пути к словарям -----------------------------------------------------------
HERE = Path(__file__).parent
DEFAULT_TERMS_PATH = HERE / "terms_by_theme.yaml"
DEFAULT_ADDITIONS = HERE / "additions.yaml"

TERMS_PATH = Path(os.getenv("TERMS_PATH", str(DEFAULT_TERMS_PATH)))
TERMS_ADDITIONS_ENV = os.getenv("TERMS_ADDITIONS")  # "path1.yaml,path2.yaml"
ADDITIONS_PATHS: List[Path] = []

if TERMS_ADDITIONS_ENV:
    ADDITIONS_PATHS = [Path(p.strip()) for p in TERMS_ADDITIONS_ENV.split(",") if p.strip()]
elif DEFAULT_ADDITIONS.exists():
    ADDITIONS_PATHS = [DEFAULT_ADDITIONS]

# --- Вспомогательные функции ---------------------------------------------------
def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path or not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _deep_merge(base: Any, add: Any) -> Any:
    if base is None:
        return add
    if add is None:
        return base
    if isinstance(base, dict) and isinstance(add, dict):
        res = dict(base)
        for k, v in add.items():
            res[k] = _deep_merge(res.get(k), v)
        return res
    if isinstance(base, list) and isinstance(add, list):
        seen = set(base)
        res = list(base)
        for item in add:
            if item not in seen:
                res.append(item)
                seen.add(item)
        return res
    return add  # скаляры — берём из additions

# --- Загрузка и подготовка словаря --------------------------------------------
SECTION_ORDER = [
    "typos",        # сначала фиксим артефакты машинного перевода
    "names", "clubs", "competitions", "positions",
    "terms",        # одно- и двухсловные термины
    "phrases",      # регэкспы и многословные обороты
    "templates",    # мягкая фанатская стилизация — в самом конце
]

def _build_literal_pattern(key: str) -> re.Pattern:
    """
    Компилируем кейс-инсENSITIVE паттерн для точной подстроки.
    Ключ экранируем. Для совсем коротких ключей (<=3) — ставим границы слова.
    """
    escaped = re.escape(key)
    if len(key) <= 3:
        pat = rf"\b{escaped}\b"
    else:
        pat = escaped
    return re.compile(pat, re.IGNORECASE | re.DOTALL)

def _compile_replacements(data: Dict[str, Dict[str, str]]) -> List[Tuple[str, re.Pattern, str]]:
    """
    Возвращает список троек: (section, compiled_pattern, replacement)
    Сортировка: внутри секции — по убыванию длины ключа.
    Для phrases — ключ считаем регуляркой как есть (IGNORECASE|DOTALL).
    Для остальных — экранированный литерал (IGNORECASE|DOTALL).
    """
    compiled: List[Tuple[str, re.Pattern, str]] = []
    for section in SECTION_ORDER:
        mapping: Dict[str, str] = data.get(section, {}) or {}
        # сортировка ключей по убыванию длины
        items = sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True)
        for key, val in items:
            if not key:
                continue
            if section == "phrases":
                try:
                    pat = re.compile(key, re.IGNORECASE | re.DOTALL)
                except re.error as e:
                    logger.warning(f"[TERMS] Некорректный regex в phrases: '{key}': {e}")
                    continue
            else:
                pat = _build_literal_pattern(key)
            compiled.append((section, pat, val))
    return compiled

def _load_terms_merged() -> Dict[str, Dict[str, str]]:
    """
    Грузит базовый terms_by_theme.yaml + все additions*, делает глубокий merge.
    Возвращает структуру вида: {section: {key: value}}.
    """
    if not TERMS_PATH.exists():
        logger.warning("⚠️ terms_by_theme.yaml not found")
        base = {}
    else:
        base = _load_yaml(TERMS_PATH)

    merged = dict(base)
    for add_path in ADDITIONS_PATHS:
        add = _load_yaml(add_path)
        if add:
            merged = _deep_merge(merged, add)
            logger.info(f"[TERMS] Merged additions: {add_path.name}")
        else:
            logger.info(f"[TERMS] Additions empty or missing: {add_path}")

    # Гарантируем наличие секций
    out: Dict[str, Dict[str, str]] = {sec: dict(merged.get(sec, {}) or {}) for sec in SECTION_ORDER}
    # Плюс — подтянем любые другие секции (если есть экзотика)
    for sec, mapping in merged.items():
        if sec not in out and isinstance(mapping, dict):
            out[sec] = dict(mapping)
    return out

# --- Компиляция замен при импорте ---------------------------------------------
_RAW_TERMS = _load_terms_merged()
_COMPILED_REPLACEMENTS = _compile_replacements(_RAW_TERMS)

def apply_custom_dictionary(text: str) -> str:
    """
    Применяет замены в фиксированном порядке секций.
    Использует case-insensitive regex подстановки.
    Логирует список ключей, по которым реально были замены.
    """
    if not text:
        return text

    result = text
    touched: List[str] = []

    for section, pattern, repl in _COMPILED_REPLACEMENTS:
        # Выполняем замену и считаем количество
        new_text, count = pattern.subn(repl, result)
        if count > 0:
            touched.append(f"{section}: '{pattern.pattern}' → '{repl}' (x{count})")
            result = new_text

    if touched:
        logger.info("[TERMS] Заменены термины:\n  - " + "\n  - ".join(touched))

    return result

# --- Переводчики ---------------------------------------------------------------
def _translate_with_google(text: str) -> str:
    return GoogleTranslator(source="auto", target="ru").translate(text)

def _translate_with_mymemory(text: str) -> str:
    return MyMemoryTranslator(source="auto", target="ru").translate(text)

def translate_text(text: str) -> str:
    """
    1) Google → 2) MyMemory (fallback) → 3) Исходный текст
    Затем: прогон через apply_custom_dictionary().
    """
    translated = None
    try:
        translated = _translate_with_google(text)
    except Exception as e:
        logger.error(f"GoogleTranslator error: {e}")

    if not translated:
        try:
            translated = _translate_with_mymemory(text)
        except Exception as e:
            logger.error(f"MyMemoryTranslator error: {e}")

    if not translated:
        translated = text

    return apply_custom_dictionary(translated)
