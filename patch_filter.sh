#!/bin/bash
set -e

cd ~/coffee-bot

echo "📂 Работаем в папке $(pwd)"

# Создание filter.py
cat > filter.py << 'PYCODE'
import re

REAL_KEYWORDS = [
    "реал мадрид", "real madrid", "галактикос", "сливочные",
    "анчелотти", "бензема", "мадридцы", "сантьяго бернабеу",
    "виннис", "родриго", "модрич", "крорус", "беллингем",
    "камавинга", "чуамени", "аренда из реала", "бывший игрок реала"
]

def is_relevant(text: str) -> bool:
    text_lower = text.lower()
    for kw in REAL_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", text_lower):
            return True
    return False
PYCODE

echo "✅ filter.py создан"

# Добавляем импорт (если нет)
if ! grep -q "from filter import is_relevant" main.py; then
    sed -i '1i from filter import is_relevant' main.py
    echo "✅ импорт добавлен"
else
    echo "ℹ️ импорт уже есть"
fi

# Добавляем проверку перед bot.send_message
if ! grep -q "if not is_relevant" main.py; then
    sed -i '/bot.send_message/a\        if not is_relevant(translated_text):\n            logging.info(f"⏩ Пропущено как нерелевантное: {translated_text[:80]}...")\n            continue' main.py
    echo "✅ проверка добавлена"
else
    echo "ℹ️ проверка уже есть"
fi

echo "🎉 Патч успешно применён!"
