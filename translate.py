from deep_translator import GoogleTranslator, MyMemoryTranslator


def translate_text(text: str) -> str:
    """
    Перевод текста на русский.
    Сначала пробуем GoogleTranslator, если ошибка — MyMemory.
    Если оба падают, возвращаем оригинал.
    """
    try:
        return GoogleTranslator(source='auto', target='ru').translate(text)
    except Exception:
        try:
            return MyMemoryTranslator(source='en', target='ru').translate(text)
        except Exception:
            return text
