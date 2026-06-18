import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)

STOPWORDS = {
    "a",
    "about",
    "after",
    "again",
    "all",
    "and",
    "are",
    "as",
    "at",
    "before",
    "but",
    "by",
    "club",
    "for",
    "from",
    "game",
    "have",
    "his",
    "in",
    "into",
    "is",
    "it",
    "its",
    "latest",
    "league",
    "madrid",
    "match",
    "new",
    "news",
    "of",
    "on",
    "player",
    "players",
    "real",
    "report",
    "reports",
    "season",
    "says",
    "said",
    "team",
    "the",
    "this",
    "to",
    "with",
    "а",
    "без",
    "в",
    "во",
    "для",
    "до",
    "его",
    "из",
    "и",
    "игра",
    "игрок",
    "игроки",
    "к",
    "как",
    "клуб",
    "лига",
    "мадрид",
    "матч",
    "на",
    "не",
    "новости",
    "о",
    "об",
    "от",
    "по",
    "после",
    "реал",
    "с",
    "сезон",
    "у",
}

ENTITY_TOKENS = {
    "alaba",
    "alexander",
    "alonso",
    "arda",
    "arnold",
    "bellingham",
    "brahim",
    "carvajal",
    "courtois",
    "endrick",
    "florentino",
    "fran",
    "guler",
    "huijsen",
    "jude",
    "kylian",
    "mbappe",
    "militao",
    "modric",
    "perez",
    "rodrygo",
    "rudiger",
    "trent",
    "valverde",
    "vini",
    "vinicius",
    "xabi",
    "алонсо",
    "арда",
    "беллингем",
    "вальверде",
    "винисиус",
    "гюлер",
    "карвахаль",
    "кортуа",
    "мбаппе",
    "модрич",
    "перес",
    "родриго",
    "рудигер",
    "трент",
    "хаби",
    "эндрик",
}

TOPIC_RULES = {
    "official": {
        "weight": 30,
        "terms": ("official", "confirmed", "comunicado", "oficial", "confirmado", "официально", "подтвержден"),
    },
    "injury": {
        "weight": 24,
        "terms": ("injury", "injured", "medical", "diagnosis", "lesion", "lesionados", "травм", "диагноз", "медицин"),
    },
    "lineup": {
        "weight": 20,
        "terms": ("lineup", "line-up", "squad", "convocatoria", "xi", "starting", "состав", "заявка", "старте"),
    },
    "matchday": {
        "weight": 18,
        "terms": ("champions", "ucl", "laliga", "liga", "fixture", "preview", "derby", "clasico", "clásico", "matchday", "лч", "лига чемпионов", "класико", "дерби"),
    },
    "transfer": {
        "weight": 16,
        "terms": ("transfer", "signing", "interest", "target", "offer", "bid", "clause", "fichaje", "mercado", "traspaso", "трансфер", "интерес", "переговор", "контракт", "аренда"),
    },
    "coach": {
        "weight": 12,
        "terms": ("coach", "manager", "ancelotti", "xabi", "alonso", "тренер", "анчилотти", "хаби", "алонсо"),
    },
}

SOURCE_WEIGHTS = (
    ("realmadrid", 12),
    ("real madrid official", 12),
    ("managing madrid", 6),
    ("madrid universal", 6),
    ("the real champs", 5),
    ("marca", 4),
    ("as", 4),
    ("relevo", 4),
    ("defensa central", 3),
)


@dataclass
class RankedDigestItem:
    candidate: Any
    grouped_links: set[str]
    related_sources: list[str]
    score: int
    reason: str


@dataclass
class CandidateProfile:
    tokens: set[str]
    entities: set[str]
    topics: set[str]
    score: int
    reason: str


@dataclass
class CandidateGroup:
    primary: Any
    profile: CandidateProfile
    members: list[Any]
    scores: dict[str, int]
    reasons: dict[str, str]


def text_attr(candidate: Any, name: str, default: str = "") -> str:
    value = getattr(candidate, name, default)
    return str(value or "")


def link_attr(candidate: Any) -> str:
    return text_attr(candidate, "link")


def source_attr(candidate: Any) -> str:
    return text_attr(candidate, "source", "Неизвестный источник")


def published_attr(candidate: Any) -> datetime | None:
    value = getattr(candidate, "published_at", None)
    return value if isinstance(value, datetime) else None


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


def tokenize(value: str) -> set[str]:
    normalized = normalize_text(value)
    return {token for token in TOKEN_RE.findall(normalized) if len(token) > 2 and token not in STOPWORDS}


def matched_topics(text: str) -> set[str]:
    normalized = normalize_text(text)
    topics = set()
    for topic, rule in TOPIC_RULES.items():
        if any(term in normalized for term in rule["terms"]):
            topics.add(topic)
    return topics


def source_weight(source: str) -> int:
    normalized = normalize_text(source)
    for marker, weight in SOURCE_WEIGHTS:
        if marker in normalized:
            return weight
    return 0


def recency_weight(published_at: datetime | None, now: datetime) -> int:
    if not published_at:
        return 0
    published = published_at.astimezone(timezone.utc)
    age_hours = max((now - published).total_seconds() / 3600, 0)
    if age_hours <= 1:
        return 8
    if age_hours <= 3:
        return 6
    if age_hours <= 6:
        return 4
    if age_hours <= 12:
        return 2
    return 0


def candidate_profile(candidate: Any, now: datetime) -> CandidateProfile:
    title = text_attr(candidate, "title")
    source = source_attr(candidate)
    tokens = tokenize(f"{title} {source}")
    entities = {token for token in tokens if token in ENTITY_TOKENS}
    topics = matched_topics(title)

    score = 50
    reasons = []
    for topic in sorted(topics):
        weight = int(TOPIC_RULES[topic]["weight"])
        score += weight
        reasons.append(topic)

    entity_bonus = min(len(entities) * 3, 12)
    if entity_bonus:
        score += entity_bonus
        reasons.append("players")

    source_bonus = source_weight(source)
    if source_bonus:
        score += source_bonus
        reasons.append("source")

    fresh_bonus = recency_weight(published_attr(candidate), now)
    if fresh_bonus:
        score += fresh_bonus
        reasons.append("fresh")

    return CandidateProfile(
        tokens=tokens,
        entities=entities,
        topics=topics,
        score=score,
        reason=", ".join(reasons) or "freshness",
    )


def token_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(min(len(left), len(right)), 1)


def similar_enough(profile: CandidateProfile, group: CandidateGroup, similarity_threshold: float) -> bool:
    overlap = token_overlap(profile.tokens, group.profile.tokens)
    if overlap >= similarity_threshold:
        return True

    shared_entities = profile.entities & group.profile.entities
    shared_topics = profile.topics & group.profile.topics
    if shared_entities and shared_topics:
        return True

    if len(shared_entities) >= 2:
        return True

    return False


def candidate_sort_key(candidate: Any, profile: CandidateProfile) -> tuple[int, datetime]:
    published = published_attr(candidate) or datetime.min.replace(tzinfo=timezone.utc)
    return profile.score, published.astimezone(timezone.utc)


def add_to_group(group: CandidateGroup, candidate: Any, profile: CandidateProfile) -> None:
    group.members.append(candidate)
    group.profile.tokens |= profile.tokens
    group.profile.entities |= profile.entities
    group.profile.topics |= profile.topics
    group.scores[link_attr(candidate)] = profile.score
    group.reasons[link_attr(candidate)] = profile.reason

    current_sort = candidate_sort_key(group.primary, group.profile)
    if candidate_sort_key(candidate, profile) > current_sort:
        group.primary = candidate
        group.profile.score = profile.score
        group.profile.reason = profile.reason


def related_sources_for_group(group: CandidateGroup) -> list[str]:
    primary_source = source_attr(group.primary).casefold()
    seen = {primary_source}
    related = []
    for candidate in group.members:
        source = source_attr(candidate)
        key = source.casefold()
        if key in seen:
            continue
        seen.add(key)
        related.append(source)
    return related


def grouped_links(group: CandidateGroup) -> set[str]:
    return {link_attr(candidate) for candidate in group.members if link_attr(candidate)}


def rank_digest_candidates(
    candidates: list[Any],
    limit: int,
    *,
    dedupe_enabled: bool = True,
    priority_sort_enabled: bool = True,
    similarity_threshold: float = 0.42,
) -> list[RankedDigestItem]:
    now = datetime.now(timezone.utc)
    profiles = {link_attr(candidate): candidate_profile(candidate, now) for candidate in candidates}

    if not dedupe_enabled:
        ranked = []
        for candidate in candidates:
            profile = profiles[link_attr(candidate)]
            ranked.append(
                RankedDigestItem(
                    candidate=candidate,
                    grouped_links={link_attr(candidate)},
                    related_sources=[],
                    score=profile.score,
                    reason=profile.reason,
                )
            )
    else:
        groups: list[CandidateGroup] = []
        for candidate in sorted(candidates, key=lambda item: candidate_sort_key(item, profiles[link_attr(item)]), reverse=True):
            profile = profiles[link_attr(candidate)]
            target = None
            for group in groups:
                if similar_enough(profile, group, similarity_threshold):
                    target = group
                    break

            if target is None:
                groups.append(
                    CandidateGroup(
                        primary=candidate,
                        profile=CandidateProfile(
                            tokens=set(profile.tokens),
                            entities=set(profile.entities),
                            topics=set(profile.topics),
                            score=profile.score,
                            reason=profile.reason,
                        ),
                        members=[candidate],
                        scores={link_attr(candidate): profile.score},
                        reasons={link_attr(candidate): profile.reason},
                    )
                )
            else:
                add_to_group(target, candidate, profile)

        ranked = []
        for group in groups:
            related_sources = related_sources_for_group(group)
            source_bonus = min(len(related_sources) * 4, 12)
            ranked.append(
                RankedDigestItem(
                    candidate=group.primary,
                    grouped_links=grouped_links(group),
                    related_sources=related_sources,
                    score=group.profile.score + source_bonus,
                    reason=group.profile.reason,
                )
            )

    if priority_sort_enabled:
        ranked.sort(
            key=lambda item: (
                item.score,
                published_attr(item.candidate) or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
    else:
        ranked.sort(
            key=lambda item: published_attr(item.candidate) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    return ranked[:limit]
