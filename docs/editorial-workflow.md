# Editorial Workflow

## Story memory

Every successfully published breaking item, digest item, and match-center update is stored in `state/editorial_archive.json`. Semantic keys merge duplicate source variants into a single storyline. Runtime state stays outside git.

## Weekly recap

`weekly_recap.py` runs from `main.py` on `WEEKLY_RECAP_DAY` and `WEEKLY_RECAP_TIME`. It only publishes after at least `WEEKLY_RECAP_MIN_ITEMS` archived stories exist, respects the matchday quiet window by default, and records the published ISO week so a restart cannot duplicate it.

## Transfer tracker

`state/transfer_tracker.json` stores player-specific market state. The deterministic statuses are `слух`, `подтвержденный интерес`, `официально`, and `опровергнуто`.

The tracker is deliberately passive by default: it supplies the weekly market block but does not publish a new Telegram post for every state transition. This keeps the channel from repeating the same transfer thread all day.

Run a local/server-side check with:

```bash
python transfer_tracker.py --summary
python weekly_recap.py --force
```

`--force` is for dry-runs and manual editorial checks; do not use it casually on a live channel because it bypasses the once-per-week guard.

## X sources

X remains disabled until `X_RSS_BASE_URL` is configured. `X_RSS_HANDLES` is an explicit whitelist. Official accounts and selected reporters are recognized by source tier; community aggregators cannot qualify a breaking post alone.

## Match Center

The automatic match flow is:

1. Day-before fixture post.
2. Matchday preview and kickoff.
3. Confirmed Real Madrid XI from API-FOOTBALL when the fixture ID is present in `config/matches.json`.
4. Approved live events from the API provider.
5. Confirmed final score from API-FOOTBALL, or the text-only fallback when live is disabled.

Set `MATCHDAY_LIVE_ENABLED=true` and provide `API_FOOTBALL_KEY` only after checking provider quotas. A fixture without `api_football_fixture_id` keeps the safe text-only path.

## Source autopilot

`source_quality.py` records candidate, selected, and quarantined counts. After a meaningful sample, a source with a high quarantine rate can become `backup`, which applies a stronger ranking penalty. Hard blocking is opt-in through `SOURCE_QUALITY_HARD_BLOCK_ENABLED=true` and remains disabled by default.
