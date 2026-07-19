from visual_cards import badge_slug, normalized_team_name, team_query_name


def test_club_badge_lookup_normalizes_names_and_keeps_known_aliases():
    assert normalized_team_name("Real Madrid") == "realmadrid"
    assert badge_slug("Real Madrid") == "realmadrid"
    assert team_query_name("Athletic Club") == "Athletic Bilbao"
    assert team_query_name("Real Madrid") == "Real Madrid"
