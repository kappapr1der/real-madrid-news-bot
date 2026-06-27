from types import SimpleNamespace

from digest import digest_llm_hard_deny, format_news_entry
from filters import passes_filters
from text_cleaner import clean_text


def _item(title: str, summary: str = ""):
    candidate = SimpleNamespace(
        title=title,
        summary=summary,
        source="test",
        link="https://example.com",
    )
    return SimpleNamespace(candidate=candidate)


def test_world_cup_player_noise_is_filtered():
    cases = [
        "Fede Valverde's Uruguay eliminated from 2026 World Cup",
        "Spain clinch first place in their group as Marc Cucurella features in win over Uruguay",
        "Courtois Belgica siguen adelante en Mundial: goleada, primeros de grupo",
        "Madrid World Cup Spotlight: Marc Cucurella and Spain scrape past the finish line against Uruguay",
        "El dato con el que Thibaut Courtois entra en la historia de Belgica",
        "Uruguay vuelve a firmar otra dolorosa eliminacion en fase de grupos",
    ]

    for title in cases:
        assert passes_filters(title, source="test") is False
        assert digest_llm_hard_deny(_item(title), title) is True


def test_basketball_is_filtered_even_when_real_madrid_is_mentioned():
    title = "Juancho Hernangomez, en el radar del Real Madrid"
    headline = "Хуанчо Эрнангомес на радаре Реала"

    assert passes_filters(title, source="test") is False
    assert digest_llm_hard_deny(_item(title), headline) is True


def test_world_cup_transfer_context_can_stay():
    title = (
        "Ramon Mon: si Olise no puede venir al Real Madrid, Florentino Perez "
        "quiere fichar a un jugador que sea gran estrella mundial"
    )
    headline = "Флорентино Перес хочет подписать звезду чемпионата мира вместо Олисе"

    assert passes_filters(title, source="test") is True
    assert digest_llm_hard_deny(_item(title), headline) is False


def test_celebrity_world_cup_noise_is_filtered():
    title = "Actor Channing Tatum attends World Cup match between Norway and France dressed as Erling Haaland"

    assert passes_filters(title, source="test") is False
    assert digest_llm_hard_deny(_item(title), title) is True


def test_digest_entry_uses_html_link():
    item = _item("Test title")
    item.candidate.source = "Test Source"
    item.candidate.link = "https://example.com/story?x=1&y=2"
    item.related_sources = []

    rendered = format_news_entry(1, item, title_override="Нормальный заголовок")

    assert '<a href="https://example.com/story?x=1&amp;y=2">' in rendered
    assert "](" not in rendered


def test_mbappe_role_headline_is_shortened():
    title = (
        "Роль, которую Килиан Мбаппе больше всего хочет получить в мадридском "
        "«Реале», наконец-то может оказаться в пределах досягаемости"
    )

    assert clean_text(title) == "Мбаппе может получить желаемую роль в «Реале»"
