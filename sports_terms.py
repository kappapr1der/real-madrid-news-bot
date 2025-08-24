SPORTS_TERMS = {
    # Общие
    "football", "soccer", "futbol", "футбол",
    "match", "game", "игра", "матч",
    "goal", "assist", "гол", "ассист",
    "coach", "manager", "тренер",
    "transfer", "подписание", "трансфер",
    "lineup", "состав", "formation", "тактика",

    # Турниры
    "champions league", "ucl", "uefa", "чемпионов",
    "la liga", "laliga", "primera", "примера",
    "copa del rey", "кубок испании",
    "supercopa", "суперкубок",

    # Игроки / роли
    "striker", "forward", "нападающий",
    "midfielder", "полузащитник",
    "defender", "защитник",
    "goalkeeper", "вратарь",

    # Специфические Real Madrid слова
    "bernabeu", "сантьяго", "мадрид", "real madrid",
    "хаби алонсо", "ancelotti", "ancelotti",
    "florentino", "перес"
}

def contains_sports_term(text: str) -> bool:
    """Проверяет, содержит ли текст спортивные слова"""
    lower_text = text.lower()
    return any(term in lower_text for term in SPORTS_TERMS)
