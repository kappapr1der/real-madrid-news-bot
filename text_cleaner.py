"""
Модуль для доочистки заголовков и текстов после перевода
"""

import re

OPEN_QUOTE = "\u00ab"
CLOSE_QUOTE = "\u00bb"
WORD_CHARS = "A-Za-zА-Яа-яЁё0-9"


def _fix_russian_quotes(text: str) -> str:
    """Normalize quotes and repair Yandex-style malformed guillemets."""
    out = []
    in_quote = False
    for char in text:
        if char in {'"', "“", "”", "„"}:
            out.append(CLOSE_QUOTE if in_quote else OPEN_QUOTE)
            in_quote = not in_quote
        else:
            out.append(char)
    text = "".join(out)

    oq = re.escape(OPEN_QUOTE)
    cq = re.escape(CLOSE_QUOTE)

    text = re.sub(rf"{oq}{{2,}}", OPEN_QUOTE, text)
    text = re.sub(rf"{cq}{{2,}}", CLOSE_QUOTE, text)
    text = re.sub(rf"{oq}\s+", OPEN_QUOTE, text)
    text = re.sub(rf"\s+{cq}", CLOSE_QUOTE, text)

    # Yandex sometimes swaps guillemets or uses an opening one as a closing one:
    # ,»Chelsea«asks -> , «Chelsea» asks
    # «Реала«на фоне -> «Реала» на фоне
    text = re.sub(rf"([,;:]\s*){cq}([^{OPEN_QUOTE}{CLOSE_QUOTE}]{{1,80}}){oq}", rf"\1{OPEN_QUOTE}\2{CLOSE_QUOTE}", text)
    text = re.sub(rf"(^|[^{WORD_CHARS}]){cq}([^{OPEN_QUOTE}{CLOSE_QUOTE}]{{1,80}}){oq}", rf"\1{OPEN_QUOTE}\2{CLOSE_QUOTE}", text)
    text = re.sub(rf"{oq}([^{OPEN_QUOTE}{CLOSE_QUOTE}]{{1,80}}){oq}(?=([,.;:!?]))", rf"{OPEN_QUOTE}\1{CLOSE_QUOTE}", text)
    text = re.sub(rf"{oq}([^{OPEN_QUOTE}{CLOSE_QUOTE}]{{1,80}}){oq}(?=\s|$)", rf"{OPEN_QUOTE}\1{CLOSE_QUOTE}", text)
    text = re.sub(rf"{oq}([^{OPEN_QUOTE}{CLOSE_QUOTE}]{{1,80}}){oq}(?=[{WORD_CHARS}])", rf"{OPEN_QUOTE}\1{CLOSE_QUOTE} ", text)
    text = re.sub(rf"([{WORD_CHARS}]){oq}(?=([,.;:!?]|\s|$))", rf"\1{CLOSE_QUOTE}", text)
    text = re.sub(rf"{cq}(?=[{WORD_CHARS}])", f"{CLOSE_QUOTE} ", text)
    text = re.sub(rf"([,.;:!?])(?=[{WORD_CHARS}{OPEN_QUOTE}])", r"\1 ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    return text


def _apply_editorial_rewrites(text: str) -> str:
    replacements = {
        "Марио Кортегана, комментатор": "Марио Кортегана, журналист",
        "Суперзвезда «Манчестер Сити» избегает вопросов мадридского «Реала»": "Звезда «Манчестер Сити» уходит от вопросов о мадридском «Реале»",
        "Мадридский «Реал» готов представить предложения о трансфере": "«Реал» готовит трансферные предложения",
        "готов представить предложения о трансфере": "готовит трансферные предложения",
        "двух звезд блокбастеров": "двух звёздных игроков",
        "двух звезд блокбастера": "двух звёздных игроков",
        "звезд блокбастеров": "звёздных игроков",
        "звезды блокбастеров": "звёздные игроки",
        "звезда блокбастера": "звёздный игрок",
        "из элитных клубов": "из топ-клубов",
        "главную цель Моуринью в обороне": "главную цель Моуринью для усиления защиты",
        "выпускника академии": "воспитанника академии",
        "«Реал» теряет контракт": "«Реал» упускает трансфер",
        "с началом Лиги": "к старту Ла Лиги",
        "контракт, но уже": "трансфер, но уже",
        "отчет": "",
        "Отчет": "",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    text = re.sub(r"\s*[–—-]\s*(отч[её]т|report)\.?$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bвариант\s*-\s*", "вариант - ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bварианты\s*-\s*", "варианты - ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,;-–—")

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

    text = _fix_russian_quotes(text)
    text = _apply_editorial_rewrites(text)
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

    # Ограничиваем длину текста (по символам) после редакторской чистки.
    max_len = 180
    if len(text) > max_len:
        cut = text[:max_len].rsplit(" ", 1)[0]
        text = cut + "…"

    # fallback-маркер: если видим подозрительное
    bad_markers = ["смотрит,", "в статиле", "со своего", "блокбастер"]
    if any(marker in text for marker in bad_markers):
        return text + " (англ.)"

    return text
