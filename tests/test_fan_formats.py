from datetime import datetime, timezone
from pathlib import Path

from digest import DigestCandidate
from feed_utils import normalize_x_media_url
from la_fabrica import is_concrete_la_fabrica_story, send_la_fabrica
from live_providers import FinalResult
from match_calendar import Match
from matchday import format_auto_message, format_event_message, format_final_result_message
from publication_registry import published_editorial_links, remember_editorial_link
from white_frame import WhiteFrame, original_x_post_url, send_white_frame, suitable_frame_title

import la_fabrica
import publication_registry
import white_frame


def marquee_match(home="Real Madrid", away="Barcelona"):
    return Match(
        id="marquee-test",
        competition="La Liga",
        home=home,
        away=away,
        kickoff=datetime(2026, 8, 23, 21, 0, tzinfo=timezone.utc),
    )


def test_marquee_matchday_copy_enriches_existing_posts_only():
    match = marquee_match()
    day_before = format_auto_message(match, "day_before")
    result = FinalResult(key="marquee", match=match, score="2:1", status="FT")
    final = format_final_result_message(result)

    assert "Перед свистком" in day_before
    assert "#ПередСвистком" in day_before
    assert "Этот вечер остался белым" in final
    assert "#ГолосБернабеу" in final


def test_ordinary_matchday_copy_stays_compact():
    match = marquee_match(away="Real Betis")
    day_before = format_auto_message(match, "day_before")
    result = FinalResult(key="ordinary", match=match, score="1:1", status="FT")

    assert "Завтра матч" in day_before
    assert "Перед свистком" not in day_before
    assert "ГолосБернабеу" not in format_final_result_message(result)


def test_day_before_match_post_is_localized_without_internal_copy():
    match = Match(
        id="ferencvaros-test",
        competition="Friendly",
        round="Pre-season",
        home="Ferencvaros",
        away="Real Madrid",
        kickoff=datetime(2026, 8, 8, 20, 0, tzinfo=timezone.utc),
        venue="Ferencvaros Stadion, Budapest",
        broadcast="Realmadrid TV",
    )

    message = format_auto_message(match, "day_before")

    assert "«Ференцварош» - «Реал»" in message
    assert "Товарищеский матч · Предсезонка" in message
    assert "8 августа, 20:00 МСК" in message
    assert "Где смотреть: Realmadrid TV" in message
    assert "Friendly" not in message
    assert "Ferencvaros Stadion" not in message
    assert "Заранее собираем" not in message


def test_live_event_copy_localizes_api_football_team_names():
    match = marquee_match(home="Ferencvaros", away="Real Madrid")
    message = format_event_message(
        match,
        "57",
        "Ferencvarosi TC отвечает: K. Kodro забивает. Счет 1:2. Мадриду нужно прибавлять.",
        "Гол",
        "1:2",
    )

    assert "«Ференцварош» отвечает" in message
    assert "«Реалу» нужно прибавлять" in message
    assert "Ferencvarosi TC" not in message
    assert "Мадриду" not in message


def test_white_frame_allows_club_moments_but_not_shop_posts():
    assert suitable_frame_title("First training session of pre-season in Valdebebas") is True
    assert suitable_frame_title("Semana 1") is True
    assert suitable_frame_title("Buy the new jersey in the official shop") is False


def test_nitter_media_proxy_url_uses_direct_twitter_cdn():
    url = "https://nitter.example/pic/amplify_video_thumb%2F123%2Fimg%2Fframe.jpg"
    assert normalize_x_media_url(url) == "https://pbs.twimg.com/amplify_video_thumb/123/img/frame.jpg"


def test_white_frame_links_to_original_x_post_not_nitter():
    assert original_x_post_url("https://nitter.example/realmadrid/status/12345#m") == "https://x.com/realmadrid/status/12345"


def test_white_frame_persists_link_for_digest_dedupe(monkeypatch, tmp_path):
    history = tmp_path / "white-history.json"
    registry = tmp_path / "editorial-links.json"
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"frame")
    monkeypatch.setattr(white_frame, "HISTORY_FILE", history)
    monkeypatch.setattr(publication_registry, "EDITORIAL_LINKS_FILE", registry)
    monkeypatch.setattr(white_frame, "cache_editorial_image", lambda url: image)
    monkeypatch.setattr(white_frame, "record_story", lambda **kwargs: kwargs)
    frame = WhiteFrame(
        title="Training at Valdebebas",
        link="https://example.test/official-frame",
        source="X - @realmadrid",
        image_url="https://example.test/frame.jpg",
    )
    posted = []

    assert send_white_frame(force=True, finder=lambda now: frame, post_photo=lambda caption, path: posted.append((caption, path)) or True)
    assert posted and posted[0][1] == image
    assert frame.link in published_editorial_links()


def test_la_fabrica_requires_specific_development_news():
    specific = DigestCandidate(
        title="Real Madrid academy striker makes first-team debut",
        link="https://example.test/debut",
        source="Managing Madrid",
        published_at=datetime.now(timezone.utc),
        summary="",
    )
    vague = DigestCandidate(
        title="Why Real Madrid have a special academy",
        link="https://example.test/vague",
        source="Managing Madrid",
        published_at=datetime.now(timezone.utc),
        summary="",
    )

    assert is_concrete_la_fabrica_story(specific) is True
    assert is_concrete_la_fabrica_story(vague) is False


def test_la_fabrica_publishes_once_and_hides_link_from_digest(monkeypatch, tmp_path):
    history = tmp_path / "academy-history.json"
    registry = tmp_path / "editorial-links.json"
    candidate = DigestCandidate(
        title="Real Madrid Castilla player earns first-team call-up",
        link="https://example.test/call-up",
        source="Marca - Real Madrid",
        published_at=datetime.now(timezone.utc),
        summary="",
    )
    monkeypatch.setattr(la_fabrica, "HISTORY_FILE", history)
    monkeypatch.setattr(publication_registry, "EDITORIAL_LINKS_FILE", registry)
    monkeypatch.setattr(la_fabrica, "story_title", lambda value: "Воспитанник получил вызов")
    monkeypatch.setattr(la_fabrica, "fetch_article_image", lambda url: "")
    monkeypatch.setattr(la_fabrica, "record_story", lambda **kwargs: kwargs)
    messages = []

    assert send_la_fabrica(
        force=True,
        candidate_fetcher=lambda cutoff: [candidate],
        send_text=lambda message: messages.append(message) or True,
    )
    assert messages and "Ла Фабрика" in messages[0]
    assert candidate.link in published_editorial_links()
