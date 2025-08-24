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
