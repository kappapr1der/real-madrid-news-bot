from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from pathlib import Path
from typing import Any

from runtime_config import (
    CLUB_BADGE_LOOKUP_TIMEOUT_SECONDS,
    CLUB_BADGE_LOOKUP_URL,
    VISUAL_CARDS_ENABLED,
    VISUAL_MATCH_CARDS_ENABLED,
    VISUAL_NEWS_CARDS_ENABLED,
    get_state_file,
)


CARD_DIR = get_state_file("visual_cards")
BADGE_DIR = get_state_file("club_badges")
REAL_MADRID_NAME = "Real Madrid"
TEAM_QUERY_ALIASES = {
    "athletic club": "Athletic Bilbao",
    "atletico madrid": "Atletico Madrid",
    "deportivo alaves": "Alaves",
    "deportivo la coruna": "Deportivo La Coruna",
    "racing santander": "Racing Santander",
}
PHASE_LABELS = {
    "day_before": "ЗАВТРА МАТЧ",
    "preview": "МАТЧ-ДЕНЬ",
    "kickoff": "МАТЧ НАЧАЛСЯ",
    "halftime": "ПЕРЕРЫВ",
    "fulltime": "ФИНАЛЬНЫЙ СВИСТ",
    "lineup": "СОСТАВЫ",
    "result": "ИТОГ МАТЧА",
}
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)
FONT_REGULAR_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def _pillow() -> tuple[Any, Any, Any, Any] | None:
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except ModuleNotFoundError:
        return None
    return Image, ImageDraw, ImageFont, ImageOps


def normalized_team_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").casefold())


def badge_slug(team_name: str) -> str:
    normalized = normalized_team_name(team_name)
    return normalized or "opponent"


def badge_cache_path(team_name: str) -> Path:
    return BADGE_DIR / f"{badge_slug(team_name)}.png"


def team_query_name(team_name: str) -> str:
    return TEAM_QUERY_ALIASES.get((team_name or "").casefold(), team_name or "")


def _requests() -> Any | None:
    try:
        import requests
    except ModuleNotFoundError:
        return None
    return requests


def _load_image(path: Path) -> Any | None:
    pillow = _pillow()
    if not pillow or not path.exists():
        return None
    image, _, _, _ = pillow
    try:
        with image.open(path) as source:
            return source.convert("RGBA")
    except (OSError, ValueError):
        return None


def _lookup_badge_url(team_name: str) -> str | None:
    requests = _requests()
    if not requests or not CLUB_BADGE_LOOKUP_URL:
        return None
    try:
        response = requests.get(
            CLUB_BADGE_LOOKUP_URL,
            params={"t": team_query_name(team_name)},
            timeout=CLUB_BADGE_LOOKUP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        rows = response.json().get("teams") or []
    except (requests.RequestException, ValueError, AttributeError):
        return None
    if not isinstance(rows, list):
        return None

    expected = normalized_team_name(team_name)
    exact = next(
        (
            row
            for row in rows
            if isinstance(row, dict) and normalized_team_name(str(row.get("strTeam") or "")) == expected
        ),
        None,
    )
    row = exact or next((row for row in rows if isinstance(row, dict)), None)
    badge_url = str((row or {}).get("strBadge") or "").strip()
    return badge_url if badge_url.startswith(("https://", "http://")) else None


def resolve_club_badge(team_name: str) -> Path | None:
    if not VISUAL_CARDS_ENABLED:
        return None
    cached = badge_cache_path(team_name)
    if _load_image(cached):
        return cached

    pillow = _pillow()
    requests = _requests()
    badge_url = _lookup_badge_url(team_name)
    if not pillow or not requests or not badge_url:
        return None
    image, _, _, _ = pillow
    try:
        response = requests.get(badge_url, timeout=CLUB_BADGE_LOOKUP_TIMEOUT_SECONDS)
        response.raise_for_status()
        with image.open(io.BytesIO(response.content)) as raw:
            badge = raw.convert("RGBA")
    except (requests.RequestException, OSError, ValueError):
        return None

    BADGE_DIR.mkdir(parents=True, exist_ok=True)
    badge.save(cached, format="PNG")
    return cached


def _font(size: int, bold: bool = True) -> Any:
    pillow = _pillow()
    if not pillow:
        return None
    _, _, image_font, _ = pillow
    candidates = FONT_CANDIDATES if bold else FONT_REGULAR_CANDIDATES
    for path in candidates:
        try:
            return image_font.truetype(path, size=size)
        except OSError:
            continue
    return image_font.load_default()


def _fit_text(draw: Any, text: str, font: Any, max_width: int) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    if draw.textbbox((0, 0), value, font=font)[2] <= max_width:
        return value
    while value and draw.textbbox((0, 0), f"{value}…", font=font)[2] > max_width:
        value = value[:-1]
    return f"{value.rstrip()}…" if value else "…"


def _paste_badge_or_fallback(canvas: Any, team_name: str, center_x: int, center_y: int) -> None:
    pillow = _pillow()
    if not pillow:
        return
    image, draw_module, _, _ = pillow
    draw = draw_module.Draw(canvas)
    badge_path = resolve_club_badge(team_name)
    badge = _load_image(badge_path) if badge_path else None
    size = 220
    if badge:
        badge.thumbnail((size, size), image.Resampling.LANCZOS)
        x = center_x - badge.width // 2
        y = center_y - badge.height // 2
        canvas.alpha_composite(badge, (x, y))
        return

    radius = 88
    draw.ellipse(
        (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
        fill="#F7F8FA",
        outline="#B59A4A",
        width=6,
    )
    initials = "".join(part[0] for part in (team_name or "?").split()[:2]).upper() or "?"
    font = _font(58)
    width = draw.textbbox((0, 0), initials, font=font)[2]
    draw.text((center_x - width // 2, center_y - 39), initials, fill="#173E78", font=font)


def _save_card(canvas: Any, key: str) -> Path:
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    path = CARD_DIR / f"{digest}.jpg"
    canvas.convert("RGB").save(path, format="JPEG", quality=92, optimize=True)
    return path


def _remote_image(url: str) -> Any | None:
    pillow = _pillow()
    requests = _requests()
    if not pillow or not requests or not url:
        return None
    image, _, _, _ = pillow
    try:
        response = requests.get(url, timeout=CLUB_BADGE_LOOKUP_TIMEOUT_SECONDS)
        response.raise_for_status()
        with image.open(io.BytesIO(response.content)) as raw:
            return raw.convert("RGBA")
    except (requests.RequestException, OSError, ValueError):
        return None


def render_news_card(article_image_url: str = "") -> Path | None:
    if not VISUAL_CARDS_ENABLED or not VISUAL_NEWS_CARDS_ENABLED:
        return None
    pillow = _pillow()
    if not pillow:
        return None
    image, draw_module, _, image_ops = pillow
    source = _remote_image(article_image_url)
    canvas = image_ops.fit(source, (1280, 640), method=image.Resampling.LANCZOS) if source else image.new("RGBA", (1280, 640), "#F8FAFC")
    draw = draw_module.Draw(canvas)
    if source:
        draw.rectangle((0, 0, 480, 640), fill=(248, 250, 252, 232))
    draw.rectangle((0, 0, 1280, 36), fill="#173E78")
    draw.rectangle((0, 36, 1280, 48), fill="#C7A34A")
    draw.rectangle((82, 112, 94, 528), fill="#173E78")
    draw.rectangle((108, 112, 120, 528), fill="#C7A34A")

    _paste_badge_or_fallback(canvas, REAL_MADRID_NAME, 1055, 318)
    brand_font = _font(44 if source else 52)
    title_font = _font(70 if source else 92)
    sub_font = _font(32, bold=False)
    draw.text((174, 172), "КОФЕ СО СЛИВКАМИ", fill="#173E78", font=brand_font)
    draw.text((174, 258), "БЕЛАЯ ЛЕНТА", fill="#1D2733", font=title_font)
    draw.text((178, 390), "Новости мадридистов", fill="#5B6675", font=sub_font)
    return _save_card(canvas, f"news-brand-v2:{article_image_url}")


def render_match_card(match: Any, phase: str = "", score: str = "") -> Path | None:
    if not VISUAL_CARDS_ENABLED or not VISUAL_MATCH_CARDS_ENABLED:
        return None
    pillow = _pillow()
    if not pillow:
        return None
    image, draw_module, _, _ = pillow
    canvas = image.new("RGBA", (1280, 720), "#F8FAFC")
    draw = draw_module.Draw(canvas)
    draw.rectangle((0, 0, 1280, 42), fill="#173E78")
    draw.rectangle((0, 42, 1280, 54), fill="#C7A34A")
    draw.rectangle((0, 660, 1280, 720), fill="#173E78")

    competition_font = _font(34)
    phase_font = _font(26)
    team_font = _font(42)
    score_font = _font(64)
    regular_font = _font(28, bold=False)
    competition = _fit_text(draw, str(getattr(match, "competition", "Матч")), competition_font, 760)
    round_name = _fit_text(draw, str(getattr(match, "round", "")), regular_font, 420)
    draw.text((70, 95), competition, fill="#173E78", font=competition_font)
    if round_name:
        right = draw.textbbox((0, 0), round_name, font=regular_font)[2]
        draw.text((1210 - right, 102), round_name, fill="#5B6675", font=regular_font)

    phase_label = PHASE_LABELS.get(phase, "МАТЧ «РЕАЛА»")
    phase_width = draw.textbbox((0, 0), phase_label, font=phase_font)[2]
    draw.text((640 - phase_width // 2, 175), phase_label, fill="#5B6675", font=phase_font)

    home = str(getattr(match, "home", "Real Madrid"))
    away = str(getattr(match, "away", "Соперник"))
    _paste_badge_or_fallback(canvas, home, 305, 360)
    _paste_badge_or_fallback(canvas, away, 975, 360)
    home_label = _fit_text(draw, home, team_font, 410)
    away_label = _fit_text(draw, away, team_font, 410)
    home_width = draw.textbbox((0, 0), home_label, font=team_font)[2]
    away_width = draw.textbbox((0, 0), away_label, font=team_font)[2]
    draw.text((305 - home_width // 2, 520), home_label, fill="#1D2733", font=team_font)
    draw.text((975 - away_width // 2, 520), away_label, fill="#1D2733", font=team_font)

    center = score or "VS"
    center_width = draw.textbbox((0, 0), center, font=score_font)[2]
    draw.text((640 - center_width // 2, 342), center, fill="#173E78", font=score_font)
    kickoff = getattr(match, "kickoff", None)
    if kickoff:
        date_label = kickoff.strftime("%d.%m · %H:%M МСК")
        date_width = draw.textbbox((0, 0), date_label, font=regular_font)[2]
        draw.text((640 - date_width // 2, 602), date_label, fill="#5B6675", font=regular_font)
    return _save_card(canvas, f"match-v1:{getattr(match, 'id', '')}:{phase}:{score}")
