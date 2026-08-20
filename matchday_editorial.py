"""Fan-first copy for the biggest Real Madrid matchdays."""

from __future__ import annotations

import re
import unicodedata

from live_providers import FinalResult
from match_calendar import Match
from runtime_config import (
    MATCHDAY_BERNABEU_VOICE_ENABLED,
    MATCHDAY_MARQUEE_COMPETITIONS,
    MATCHDAY_MARQUEE_ENABLED,
    MATCHDAY_MARQUEE_OPPONENTS,
    MATCHDAY_PRE_WHISTLE_ENABLED,
)


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", plain.casefold())


def opponent_name(match: Match) -> str:
    return match.away if match.is_home else match.home


def is_marquee_match(match: Match) -> bool:
    if not MATCHDAY_MARQUEE_ENABLED:
        return False
    opponent = _normalized(opponent_name(match))
    competition = _normalized(match.competition)
    return any(_normalized(value) in opponent for value in MATCHDAY_MARQUEE_OPPONENTS) or any(
        _normalized(value) in competition for value in MATCHDAY_MARQUEE_COMPETITIONS
    )


def pre_whistle_copy(match: Match) -> str:
    if not MATCHDAY_PRE_WHISTLE_ENABLED or not is_marquee_match(match):
        return ""
    if match.is_home:
        return "Большой вечер уже близко: Бернабеу готовится к матчу, который не нуждается в лишних словах."
    return "Большой вечер уже близко: Мадрид едет на матч, где детали обычно решают все."


def _real_score(result: FinalResult) -> tuple[int, int] | None:
    values = re.findall(r"\d+", result.score or "")
    if len(values) < 2:
        return None
    home, away = int(values[0]), int(values[1])
    return (home, away) if result.match.is_home else (away, home)


def bernabeu_voice_copy(result: FinalResult) -> str:
    if not MATCHDAY_BERNABEU_VOICE_ENABLED or not is_marquee_match(result.match):
        return ""
    score = _real_score(result)
    if not score:
        return "Финальный свисток уже прозвучал. Эмоции улягутся, а разговор о матче только начинается."
    real_goals, opponent_goals = score
    if real_goals > opponent_goals:
        return "Этот вечер остался белым. Спокойно забрали свое, а детали разберем уже после эмоций."
    if real_goals < opponent_goals:
        return "Тяжелая ночь. Но один матч не отменяет сезон и не меняет право требовать от Мадрида большего."
    return "Ничья оставила недосказанность. Счет зафиксирован, а вопросы к следующему матчу уже появились."
