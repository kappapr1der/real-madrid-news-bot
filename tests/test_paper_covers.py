import paper_covers
from datetime import date


class FakeResponse:
    headers = {"content-type": "text/html"}

    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_as_cover_uses_the_first_newest_first_gallery_image(monkeypatch):
    html = """
    <img src="https://static.as.com/logo.jpg">
    <img src="https://img.asmedia.epimg.net/resizer/v2/LATEST.jpg?auth=token&amp;width=375">
    <img src="https://img.asmedia.epimg.net/resizer/v2/OLDER.jpg?auth=token&amp;width=375">
    """
    monkeypatch.setattr(paper_covers.requests, "get", lambda *_args, **_kwargs: FakeResponse(html))

    cover = paper_covers.fetch_latest_as_cover("https://as.example.test/covers")

    assert cover is not None
    assert cover.source_name == "Diario AS"
    assert "LATEST.jpg" in cover.image_url
    assert "width=1200" in cover.image_url


def test_as_cover_archive_url_tracks_the_current_month():
    assert paper_covers.as_cover_archive_url(date(2026, 7, 19)).endswith("de-julio-f202607-f/")
    assert paper_covers.as_cover_archive_url(date(2026, 8, 1)).endswith("de-agosto-f202608-f/")
