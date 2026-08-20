import visual_cards
from visual_cards import badge_slug, normalized_team_name, render_x_post_card, team_query_name


def test_club_badge_lookup_normalizes_names_and_keeps_known_aliases():
    assert normalized_team_name("Real Madrid") == "realmadrid"
    assert badge_slug("Real Madrid") == "realmadrid"
    assert team_query_name("Athletic Club") == "Athletic Bilbao"
    assert team_query_name("Real Madrid") == "Real Madrid"


def test_x_post_card_renders_a_fixed_visual_for_a_curated_account(monkeypatch, tmp_path):
    monkeypatch.setattr(visual_cards, "CARD_DIR", tmp_path)
    monkeypatch.setattr(visual_cards, "resolve_club_badge", lambda _team: None)
    card = render_x_post_card(
        "X – @realmadrid",
        "«Реал» объявил состав на ближайший матч.",
    )

    assert card is not None
    assert card.exists()
    with visual_cards._pillow()[0].open(card) as image:
        assert image.size == (1080, 1350)
