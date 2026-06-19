"""
Модуль для доочистки заголовков и текстов после перевода
"""

import re


def _fix_russian_quotes(text: str) -> str:
    """Normalize quotes and repair Yandex-style malformed guillemets."""
    out = []
    in_quote = False
    for char in text:
        if char in {'"', '“', '”'}:
            out.append("»" if in_quote else "«")
            in_quote = not in_quote
        else:
            out.append(char)
    text = "".join(out)

    text = re.sub(r"«{2,}", "«", text)
    text = re.sub(r"»{2,}", "»", text)
    text = re.sub(r"«\s+", "«", text)
    text = re.sub(r"\s+»", "»", text)

    # Yandex sometimes uses an opening guillemet where a closing one is needed:
    # «Реала«на фоне -> «Реала» на фоне
    text = re.sub(r"«([^«»]{1,80})«(?=([,.;:!?]))", r"«\1»", text)
    text = re.sub(r"«([^«»]{1,80})«(?=\s|$)", r"«\1»", text)
    text = re.sub(r"«([^«»]{1,80})«(?=[A-Za-zА-Яа-яЁё0-9])", r"«\1» ", text)
    text = re.sub(r"»«(?=[A-Za-zА-Яа-яЁё0-9])", "» ", text)
    text = re.sub(r"([A-Za-zА-Яа-яЁё0-9])«(?=([,.;:!?]|\s|$))", r"\1»", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)

    return text


def clean_text(text: str) -> str:
    # Базовые замены
    replacements = {
        # Футбол
        "в Реал -Мадриде": "в «Реале»",
        "Реал Мадрид": "«Реал»",
        "Барселона": "«Барселона»",
        "Манчестер Юнайтед": "«Манчестер Юнайтед»",
        "Арсенал": "«Арсенал»",
        "Ливерпуль": "«Ливерпуль»",

        # Типичные кривые переводы
        "смотрит, чтобы продолжить": "продолжит",
        "отвечает на то, что": "о",
        "остаются в статиле": "застопорились",
        "со своего лунного шара": "лунного удара",
        "источник сообщил": "источник рассказал",
        "взвешивает прогресс": "оценил прогресс",

        # Чистим повторы
        "предложение по контракту": "контракт",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    # Приводим все формы с "Реалом" к кавычкам
    forms = {
        r"\bв Реале\b": "в «Реале»",
        r"\bиз Реала\b": "из «Реала»",
        r"\bо Реале\b": "о «Реале»",
        r"\bдля Реала\b": "для «Реала»",
        r"\bк Реалу\b": "к «Реалу»",
        r"\bс Реалом\b": "с «Реалом»",
        r"\bпротив Реала\b": "против «Реала»",
        r"\bнад Реалом\b": "над «Реалом»",
        r"\bу Реала\b": "у «Реала»",
        r"\bпо Реалу\b": "по «Реалу»",
    }
    for pattern, repl in forms.items():
        text = re.sub(pattern, repl, text)

    # Чистим мусорные хвосты
    text = re.sub(r"\s*\(?(VIDEO|ФОТО|Фото|ВИДЕО)\)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\[LIVE\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*[-–—]\s*подробности.*$", "", text, flags=re.IGNORECASE)

    # Убираем повторы слов подряд ("Реал Реал" -> "Реал")
    text = re.sub(r"\b(\w+)( \1\b)+", r"\1", text, flags=re.IGNORECASE)

    # Ограничиваем длину текста (по символам)
    max_len = 180
    if len(text) > max_len:
        cut = text[:max_len].rsplit(" ", 1)[0]
        text = cut + "…"

    text = _fix_russian_quotes(text)

    # Убираем эмодзи (любые юникодные пиктограммы)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002700-\U000027BF"
        "\U0001F900-\U0001F9FF"
        "\U00002600-\U000026FF"
        "]+",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub("", text)

    # Чистим лишние пробелы и переносы
    text = re.sub(r"\s+", " ", text).strip()

    # fallback-маркер: если видим подозрительное
    bad_markers = ["смотрит,", "в статиле", "со своего"]
    if any(marker in text for marker in bad_markers):
        return text + " (англ.)"

    return text
