from datetime import datetime, timedelta, timezone

import breaking
import breaking_confirmation
from fabrizio_source import parse_fabrizio_telegram_html
from source_quality import source_trust_tier


def test_fabrizio_telegram_parser_returns_newest_entries_first():
    html = """
    <div class="tgme_widget_message">
      <div class="tgme_widget_message_text">Older transfer update</div>
      <a class="tgme_widget_message_date" href="https://t.me/FabrizioRomanoTG/1"></a>
      <time datetime="2026-07-19T10:00:00+00:00"></time>
    </div>
    <div class="tgme_widget_message">
      <div class="tgme_widget_message_text">Newer transfer update</div>
      <a class="tgme_widget_message_date" href="https://t.me/FabrizioRomanoTG/2"></a>
      <time datetime="2026-07-19T11:00:00+00:00"></time>
    </div>
    """

    entries = parse_fabrizio_telegram_html(html)

    assert [entry["link"] for entry in entries] == [
        "https://t.me/FabrizioRomanoTG/2",
        "https://t.me/FabrizioRomanoTG/1",
    ]


def test_here_we_go_requires_fabrizio_and_real_madrid_transfer():
    title = "Real Madrid complete deal for Michael Olise, here we go! Agreement signed."

    assert source_trust_tier("Fabrizio Romano - Telegram") == "reporter"
    assert breaking.is_here_we_go(title, "Fabrizio Romano - Telegram") is True
    assert breaking.is_here_we_go(title, "Madrid Universal") is False
    assert breaking.is_here_we_go("Here we go, new YouTube episode", "Fabrizio Romano - Telegram") is False


def test_here_we_go_bypasses_confirmation_and_keeps_short_freshness_window(monkeypatch, tmp_path):
    monkeypatch.setattr(breaking_confirmation, "CONFIRMATIONS_FILE", tmp_path / "confirmations.json")
    decision = breaking_confirmation.observe_breaking_candidate(
        fingerprint="transfer:olise-real",
        source="Fabrizio Romano - Telegram",
        trusted_reporter=True,
    )

    assert decision.ready is True
    assert decision.reason == "trusted_reporter"
    assert breaking.here_we_go_is_fresh({"published_at": datetime.now(timezone.utc) - timedelta(minutes=20)}) is True
    assert breaking.here_we_go_is_fresh({"published_at": datetime.now(timezone.utc) - timedelta(hours=4)}) is False


def test_here_we_go_bootstrap_remembers_current_channel_without_posting(monkeypatch, tmp_path):
    monkeypatch.setattr(breaking, "HERE_WE_GO_BOOTSTRAP_FILE", tmp_path / "bootstrap.txt")
    entries = [{"link": "https://t.me/FabrizioRomanoTG/1"}, {"link": "https://t.me/FabrizioRomanoTG/2"}]

    assert breaking.bootstrap_here_we_go(entries) is True
    assert breaking.bootstrap_here_we_go(entries) is False
    assert breaking.load_sent_links(breaking.HERE_WE_GO_BOOTSTRAP_FILE) == {
        "https://t.me/FabrizioRomanoTG/1",
        "https://t.me/FabrizioRomanoTG/2",
    }
