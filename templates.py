import random

# Шаблоны для breaking news
BREAKING_TEMPLATES = [
    "☕️ Сливочная молния\n{news}\n🔗 {link}",
    "⚪️ Экстра от «Кофе со сливками»\n{news}\n🔗 {link}",
    "🚨 Горячо из чашки сливочного кофе\n{news}\n🔗 {link}",
    "🔥 Срочно! Новости Реала:\n{news}\n🔗 {link}",
    "🏰 Новости замка Мадрида:\n{news}\n🔗 {link}",
    "✨ В центре внимания:\n{news}\n🔗 {link}",
    "💥 Брызги на поле:\n{news}\n🔗 {link}",
    "📣 Эй, фанаты Реала:\n{news}\n🔗 {link}",
    "⚡️ Breaking из Мадрида:\n{news}\n🔗 {link}",
    "🏃 Быстрое обновление:\n{news}\n🔗 {link}",
    "📰 Горячие новости:\n{news}\n🔗 {link}",
    "🌟 Эксклюзив от «Кофе со сливками»:\n{news}\n🔗 {link}"
]

# Шаблоны по времени суток (для digest)
DIGEST_TEMPLATES = {
    "morning": [
        "☕️ Утренний сливочный дайджест:\n\n{news}",
        "🌅 Доброе мадридское утро:\n\n{news}",
        "📋 Дайджест Реала:\n\n{news}",
        "📰 Всё самое важное к завтраку:\n\n{news}",
        "⚪️ Новости утра из замка Реала:\n\n{news}",
        "✨ Начинаем день с Реалом:\n\n{news}",
        "🏟 Сливочное пробуждение:\n\n{news}",
        "🥐 Утренняя подборка к кофе:\n\n{news}"
    ],
    "day": [
        "🔥 Дневной обзор новостей Реала:\n\n{news}",
        "⚪️ Дневная подборка от «Кофе со сливками»:\n\n{news}",
        "📣 Новости середины дня:\n\n{news}",
        "🚨 Всё самое горячее к обеду:\n\n{news}",
        "☀️ Середина дня в Мадриде:\n\n{news}",
        "⚡️ Сливочная динамика дня:\n\n{news}",
        "📊 Обновления дня:\n\n{news}",
        "🎯 Главные события к этому часу:\n\n{news}"
    ],
    "evening": [
        "🏰 Вечерняя сливочная хроника:\n\n{news}",
        "🌙 Вечерние сливки дня:\n\n{news}",
        "📰 Итоги дня:\n\n{news}",
        "🏆 Главные победы и поражения:\n\n{news}",
        "⚡️ Самые громкие события дня:\n\n{news}",
        "📊 Итоговый отчёт:\n\n{news}",
        "🍷 Спокойный вечер с Реалом:\n\n{news}",
        "🔥 Заключительный сливочный акцент:\n\n{news}"
    ]
}

def choose_breaking(news: str, link: str) -> str:
    """Выбирает случайный шаблон для breaking"""
    template = random.choice(BREAKING_TEMPLATES)
    return template.format(news=news, link=link)

def choose_digest(part_of_day: str, news: str) -> str:
    """Выбирает случайный шаблон для дайджеста (утро/день/вечер)"""
    templates = DIGEST_TEMPLATES.get(part_of_day, [])
    if not templates:
        return news
    return random.choice(templates).format(news=news)
