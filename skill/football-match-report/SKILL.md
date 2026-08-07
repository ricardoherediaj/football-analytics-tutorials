---
name: football-match-report
description: Build a match report (scrape + dashboard) from a WhoScored URL.
version: 1.0.0
author: Ricardo Heredia (ricardoherediaj), Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [football, analytics, scraping, visualization, mplsoccer]
    related_skills: [hermes-agent-skill-authoring]
---

# Football Match Report Skill

Turns **any** WhoScored match URL into a polished match report by merging two
data sources automatically:

- **WhoScored** (headless Chromium) → the full event stream: passes, tackles,
  carries, recoveries with coordinates. Powers the passing networks,
  defensive-action heatmaps, progressive passes and event-derived stats.
- **FotMob** (plain requests, no token) → shots with xG, the native momentum
  series, official match stats, player of the match, and **real team colors**.

The FotMob match id is auto-resolved from the WhoScored match date + team
names, so a single WhoScored URL is all you need — no hardcoded team ids,
no manual pairing. Both sources are required for the complete report; a
FotMob-only bundle (pass `--fotmob-id`) renders a reduced report (shot map,
xG timeline, momentum, stats) without the event panels.

No API keys, no manual Selenium sessions, no rotating tokens.

Two commands, end to end:

```bash
python scripts/scrape_match.py "<whoscored-url>" --out ./data
python scripts/render_report.py --data ./data --out ./report
```

## When to Use

- A user asks for a post-match report, match dashboard, or football analytics
  breakdown and provides a WhoScored match URL (or match id).
- A recurring match-report job (e.g. after each round of fixtures).
- Rebuilding/updating an old notebook-based report into the modern pipeline.

Don't use for: season-long datasets (use `soccerdata`/StatsBomb open data),
live in-play streams, or non-WhoScored competitions (Understat etc.).

## Prerequisites

- Python 3.10+ with `uv` (or pip).
- Install deps: `uv sync` in the repo, or
  `uv pip install pandas numpy matplotlib mplsoccer scipy requests playwright`.
- One-time browser install: `playwright install chromium`
  (needed because WhoScored is behind a bot wall; the script launches a
  headless Chromium to read the embedded matchCentreData JSON).
- No API keys. FotMob's public endpoint (`/api/data/matchDetails`) is used
  for shots/xG/momentum/team colors and does not require a token.

## How to Run

### 1. Scrape (network required, ~10-30s)

```bash
python scripts/scrape_match.py \
  "https://www.whoscored.com/matches/1873310/live/international-fifa-club-world-cup-2025-salzburg-real-madrid" \
  --out ./data
```

Produces `data/{matchdict.json, events.csv, shots.csv, meta.json, xt_grid.csv}`.
The pipeline fetches the WhoScored event stream with headless Chromium, then
**auto-resolves the FotMob match id** from the match date + team names and
merges the FotMob shots/xG/momentum/colors. Pass `--fotmob-id <id>` to skip
resolution, or `--no-browser` to reuse an existing `matchdict.json` when
WhoScored is unreachable.

**Any match works** — teams, colors, scores and stats all come from the
scraped data; nothing is hardcoded per match. Tested on Club World Cup and
Premier League matches.

### 2. Render (offline, a few seconds)

```bash
python scripts/render_report.py --data ./data --out ./report --theme cobalt
```

Produces `report/match_report.png` and `report/match_report.html`
(themes: `cobalt` default dark navy, `midnight` classic dark, `paper` light).

### 3. Full pipeline in one line

```bash
python scripts/scrape_match.py "<url>" --out ./data \
  && python scripts/render_report.py --data ./data --out ./report
```

## Quick Reference

| Task | Command |
|------|---------|
| Scrape any match (WhoScored + FotMob auto-merged) | `python scripts/scrape_match.py "<whoscored-url>" --out ./data` |
| Render report | `python scripts/render_report.py --data ./data --out ./report` |
| Explicit FotMob id | `... --fotmob-id 4685754` |
| FotMob-only reduced bundle (no browser) | `python scripts/scrape_match.py --fotmob-id 4685754 --out ./data` |
| Skip browser (reuse cache) | `... --no-browser` |
| PNG only | `python scripts/render_report.py --data ./data --no-html` |
| Light theme | `python scripts/render_report.py --theme paper` |

## Procedure

1. **Confirm the URL is a WhoScored live/match URL.** The match id is the
   number after `/matches/` (e.g. `1873310`). If the user only has a FotMob
   link or match id, `scrape_match.py --fotmob-id <id>` still works but the
   WhoScored event stream will be missing (passing networks etc. degrade).
2. **Run the scrape** (command above). Completion criterion: `events.csv`
   exists with 500+ rows and `meta.json` has `teams.home.name`.
3. **Run the render** (command above). Completion criterion: both
   `match_report.png` and `match_report.html` exist in the output dir.
4. **Inspect the PNG** (`vision_analyze` in Hermes) for empty panels or
   overlapping text; the most common failure is a missing FotMob id, which
   leaves the shot map and xG timeline empty — re-scrape with `--fotmob-id`.
5. **Deliver** the PNG inline and the HTML path to the user.

## Metrics included

- **Passing network** per team (nodes = avg positions, edges = completed
  pass combos, thickness ∝ volume).
- **Shot map** with marker size ∝ xG, filled = on target, goals starred.
- **Defensive actions** KDE heatmap with player nodes.
- **Progressive passes** (successful passes advancing ≥10m from the middle
  third, set pieces excluded) with final-third zone split.
- **xG timeline** (cumulative, from FotMob shots) and **match momentum**
  (FotMob native series) when FotMob data is present.
- **Stats comparison**: possession, pass accuracy, tackles, interceptions,
  clearances, aerials, PPDA, field tilt, high turnovers, progressive passes.

See `references/metrics.md` for definitions and interpretation notes.

## Pitfalls

- **Both sources are needed for the full report.** WhoScored supplies the
  event stream (passing networks, defensive actions, progressive passes);
  FotMob supplies shots/xG/momentum/colors. A FotMob-only scrape
  (`--fotmob-id`) renders a reduced report without the event panels.
- **WhoScored blocks plain requests (403).** Always use the Playwright path;
  if `playwright install chromium` was skipped, the script exits with
  install instructions. `--no-browser` only works when `matchdict.json`
  already exists in the data dir.
- **FotMob coordinates are 0-100**, not StatsBomb 120x80 — `render_report.py`
  converts them (`x/100*120`). Legacy WhoScored event CSVs (0-100) are
  auto-detected and converted too.
- **FotMob match id resolution needs the match date.** If the match is older
  than ~2 years or the date endpoint returns nothing, pass `--fotmob-id`
  explicitly (find it from the FotMob match URL `#<id>`).
- **Empty shot map = missing FotMob id.** The event-based panels still render;
  only the shot/xG/momentum panels degrade.
- **Player names in passing networks** come from WhoScored's
  `playerIdNameDictionary`; without `matchdict.json` only counts are shown.
- Be polite: scrape one match at a time; don't loop over hundreds of URLs —
  WhoScored and FotMob will rate-limit or block.

## Verification

- `scrape_match.py` prints per-step status lines and a final
  `✅ Done in Xs. Bundle ready in ...` — no exceptions and both CSVs written.
- `render_report.py` prints `✅ Dashboard -> ...` and `✅ HTML report -> ...`.
- Open `match_report.png`: every panel populated (shot map/xG only when a
  FotMob id was resolved), no overlapping titles, team colors consistent
  (home color left, away right) across header and panels.
- Open `match_report.html`: embedded PNG visible, stats table non-empty,
  at least one takeaway bullet.
