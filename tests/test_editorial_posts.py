from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import editorial_posts
from editorial_posts import (
    HistoryEvent,
    PaperCover,
    format_cover_caption,
    history_events_for_day,
    load_history_events,
    send_editorial_cover,
    send_history_post,
)


TZ = ZoneInfo("Europe/Moscow")


def test_history_loader_keeps_only_valid_dates_and_selects_today(tmp_path: Path):
    fixture = tmp_path / "history.json"
    fixture.write_text(
        """{
          "events": [
            {"id":"salgado","month":7,"day":19,"year":1999,"title":"Сальгадо","description":"Представлен в Мадриде"},
            {"id":"bad","month":20,"day":7,"year":1999,"title":"Плохая дата","description":"Не попадет в архив"}
          ]
        }""",
        encoding="utf-8",
    )

    events = load_history_events(fixture)
    selected = history_events_for_day(events, datetime(2026, 7, 19, 10, tzinfo=TZ))

    assert [event.id for event in events] == ["salgado"]
    assert [event.id for event in selected] == ["salgado"]
    assert selected[0].date_label == "19 июля 1999"


def test_history_post_publishes_vetted_photo_once_without_touching_news_state(monkeypatch, tmp_path: Path):
    event = HistoryEvent(
        id="salgado",
        month=7,
        day=19,
        year=1999,
        title="Мичел Сальгадо представлен в «Реале»",
        description="Правый защитник начал белую главу карьеры.",
        image_url="https://images.example.test/salgado.jpg",
    )
    monkeypatch.setattr(editorial_posts, "load_history_events", lambda: [event])
    monkeypatch.setattr(editorial_posts, "HISTORY_POSTS_FILE", tmp_path / "history_posts.json")
    monkeypatch.setattr(editorial_posts, "cache_editorial_image", lambda _url: tmp_path / "history.jpg")
    monkeypatch.setattr(editorial_posts, "digest_block_reason", lambda: "")
    monkeypatch.setattr(editorial_posts, "record_story", lambda **_kwargs: {})
    published = []

    assert send_history_post(
        now=datetime(2026, 7, 19, 10, 30, tzinfo=TZ),
        post_photo=lambda caption, card: published.append((caption, card)) or True,
    )
    assert "<b>День в истории</b>" in published[0][0]
    assert not send_history_post(
        now=datetime(2026, 7, 19, 10, 31, tzinfo=TZ),
        post_photo=lambda *_args: True,
    )


def test_history_post_skips_an_event_without_a_vetted_photo(monkeypatch):
    event = HistoryEvent(
        id="no-photo",
        month=7,
        day=19,
        year=1999,
        title="No photo",
        description="No photo should mean no post.",
    )
    monkeypatch.setattr(editorial_posts, "load_history_events", lambda: [event])
    monkeypatch.setattr(editorial_posts, "cache_editorial_image", lambda _url: (_ for _ in ()).throw(AssertionError()))

    assert not send_history_post(
        force=True,
        now=datetime(2026, 7, 19, 10, 30, tzinfo=TZ),
        post_photo=lambda *_args: True,
    )


def test_editorial_cover_posts_the_actual_front_page(monkeypatch, tmp_path: Path):
    cover = PaperCover(
        source_name="Diario AS",
        page_url="https://as.example.test/covers",
        image_url="https://as.example.test/cover.jpg",
    )
    monkeypatch.setattr(editorial_posts, "COVER_HISTORY_FILE", tmp_path / "cover.json")
    monkeypatch.setattr(editorial_posts, "digest_block_reason", lambda: "")
    monkeypatch.setattr(editorial_posts, "cache_editorial_image", lambda _url: tmp_path / "cover.jpg")
    monkeypatch.setattr(editorial_posts, "record_story", lambda **_kwargs: {})

    assert send_editorial_cover(
        now=datetime(2026, 7, 19, 11, 30, tzinfo=TZ),
        cover_fetcher=lambda: cover,
        post_photo=lambda caption, image: "#ОбложкаДня" in caption and image == tmp_path / "cover.jpg",
    )
    assert "Открыть архив" in format_cover_caption(cover)
