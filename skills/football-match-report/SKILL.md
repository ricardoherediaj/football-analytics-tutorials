---
name: football-match-report
description: Build post-match team + player reports (24-chart dashboard, per-player dashboards, stats CSV) from a WhoScored URL.
version: 2.2.0
author: Ricardo Heredia (ricardoherediaj), Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [football, analytics, scraping, visualization, mplsoccer]
    related_skills: [hermes-agent-skill-authoring]
---

# Football Match Report Skill

Turns **any** WhoScored match URL into a two-page post-match team report by
merging two data sources:

- **WhoScored** (headless Chromium) → full event stream (passes, tackles,
  carries, recoveries). Powers passing networks, defensive blocks,
  progressive passes/carries, xT momentum and all zone charts.
- **FotMob** (plain requests, no token) → shots with xG/xGOT, native match
  momentum, official stats, player of the match, and **real team colors**.

The FotMob match id is auto-resolved from the WhoScored match date + team
names — a single WhoScored URL is all you need. Both sources are required
for the complete report; a FotMob-only scrape (`--fotmob-id`) renders a
reduced report (shots/momentum/stats) without the event panels.

Charts follow the **Post-Match-Report-2.0 blueprint** (Adnan Ahmed): UEFA
pitch, black background, shirt numbers inside player nodes
(circle = starter, box = sub), line-height markers, xT momentum.

Two commands, end to end:

```bash
python scripts/scrape_match.py "<whoscored-url>" --out ./data
python scripts/render_report.py --data ./data --out ./report
```

A third command adds the player-level reports (Top Players dashboard,
per-player dashboards, per-player stats CSV):

```bash
uv run football-match-report players --data ./data --out ./report
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
- Install deps: `uv sync --extra scrape` (or `pip install -e ".[scrape]"`).
- One-time browser install: `uv run playwright install chromium`
  (WhoScored is bot-walled; the script launches headless Chromium to read
  the embedded matchCentreData JSON).
- No API keys. FotMob's public endpoint (`/api/data/matchDetails`) is used
  for shots/xG/momentum/colors and does not require a token.

## How to Run

### 1. Scrape (network required, ~10-30s)

```bash
python scripts/scrape_match.py \
  "https://www.whoscored.com/matches/1873310/live/international-fifa-club-world-cup-2025-salzburg-real-madrid" \
  --out ./data
```

Produces `data/{matchdict.json, events.csv, shots.csv, meta.json, xt_grid.csv}`.
The FotMob match id is auto-resolved from date + team names. Pass
`--fotmob-id <id>` to skip resolution, or `--no-browser` to reuse a cached
`matchdict.json`. **Any match works** — teams, colors, scores and stats all
come from the scraped data; nothing is hardcoded per match.

### 2. Render (offline, a few seconds)

```bash
python scripts/render_report.py --data ./data --out ./report
```

Produces two 4x3 report figures:

- `report/match_report_1.png` — **Team report**: passing networks, shot map
  with xG stats bar, defensive blocks, goalkeeper saves, progressive passes,
  **xT momentum**, progressive carries, match stats.
- `report/match_report_2.png` — **Zones report**: final-third entries, box
  entries, Zone 14 & half-spaces, crosses, pass-end-zone heatmaps, high
  turnovers, chance-creating zones, congestion map.

### 3. Player-level reports (offline, optional)

```bash
uv run football-match-report players --data ./data --out ./report
# or, only specific players:
uv run football-match-report players --data ./data --out ./report \
  --players "Lamine Yamal,Mikel Oyarzabal"
```

Produces:

- `report/match_report_3.png` — **Top Players dashboard** (4x3): top ball
  progressor pass maps, passes received by the center-forward, top
  defender actions, goalkeeper pass maps + Top10 stacked bar charts
  (ball progressors, shot-sequence involvement, defenders, threat
  creators via xT).
- `report/players/<name>.png` — one **2x3 individual dashboard** per
  starter (or the names in `--players`): pass map, carries & take-ons,
  shot map with xG/xGOT, passes received, defensive actions, touches
  heatmap with distance covered.
- `report/player_stats.csv` — merged wide per-player stat table.

### 4. As a CLI (same thing)

```bash
uv run football-match-report scrape "<whoscored-url>" --out ./data
uv run football-match-report render --data ./data --out ./report
```

## Quick Reference

| Task | Command |
|------|---------|
| Scrape any match (WhoScored + FotMob auto-merged) | `python scripts/scrape_match.py "<whoscored-url>" --out ./data` |
| Render both report pages | `python scripts/render_report.py --data ./data --out ./report` |
| Render player-level reports (top players + per player + CSV) | `uv run football-match-report players --data ./data --out ./report` |
| Limit per-player dashboards to specific names | `... players --players "Lamine Yamal,Mikel Oyarzabal"` |
| Explicit FotMob id | `... --fotmob-id 4685754` |
| FotMob-only reduced bundle (no browser) | `python scripts/scrape_match.py --fotmob-id 4685754 --out ./data` |
| Skip browser (reuse cache) | `... --no-browser` |
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check src tests` |

## Procedure

1. **Confirm the URL is a WhoScored match URL.** The match id is the number
   after `/matches/`. If the user only has a FotMob link or id,
   `--fotmob-id` still works but event panels degrade.
2. **Run the scrape** (command above). Completion criterion: `events.csv`
   exists with 500+ rows and `meta.json` has `teams.home.name`.
3. **Run the render** (command above). Completion criterion: both
   `match_report_1.png` and `match_report_2.png` exist.
4. **Inspect the PNGs** (`vision_analyze` in Hermes) for empty panels or
   overlapping text. The most common failure is a missing FotMob id, which
   empties the shot map, xT momentum and GK panels — re-scrape with
   `--fotmob-id`.
5. **Deliver** both PNGs inline to the user.

## Metrics included (per team)

- **Passing network** — nodes at median positions with shirt numbers,
  circle = starter / square = sub, line thickness ∝ pass volume, verticality
  %, defensive/forward line heights + shaded zone.
- **Shot map** — football markers for goals, hatched saves, orange posts,
  big-chance scaling, plus a Goals/xG/xGOT/Shots/On Target/BigChance/
  BigC.Miss/xG-Shot/Avg.Dist comparison bar.
- **Defensive block** — KDE heatmap, action-height line, compactness %.
- **Goalkeeper saves** — goal-mouth view of shots faced per keeper.
- **Progressive passes & carries** — comet lines / dashed arrows with
  left-center-right zone split.
- **xT momentum** — average xT per minute (home above / away below zero)
  with goal and red-card markers.
- **Match stats** — possession, field tilt, passes, long balls, corners,
  GK kick length, tackles, interceptions, clearances, aerials, PPDA.
- **Zone charts** — final-third entries (by pass/carry), box entries,
  Zone 14 & half-space passes, crosses (acc./unacc.), pass-end-zone
  heatmaps, high turnovers (led to goal/shot), chance-creating zones
  (key passes = violet, assists = green), congestion map.
- **Top Players dashboard** (figure 3) — top ball progressor pass maps
  (all/progressive/key/assist passes + progressive carries), passes
  received by the center-forward, top defender action maps, GK pass maps
  (open play vs goal kicks/free kicks), Top10 stacked bars: ball
  progressors, shot-sequence involvement, defenders, xT threat creators.
- **Individual player dashboard** — pass map (accuracy, progressive,
  chances created, assists, final third, penalty box, crosses, longballs,
  xT), carries & take-ons (progressive, led to shot/goal, box entries,
  dispossessed, success rate), shot map with xG/xGOT (FotMob) and
  inside/outside box split, passes received (final third, box,
  progressive, cutbacks, ball retention, most passes from), defensive
  actions (tackles won, dribbles past, recoveries, blocks, aerials,
  possession wins per third), touches heatmap with distance covered and
  area covered.

See `references/metrics.md` for definitions and interpretation notes.

## Pitfalls

- **Both sources are needed for the full report.** WhoScored supplies the
  event stream; FotMob supplies shots/xG/momentum/colors. A FotMob-only
  scrape renders a reduced report.
- **WhoScored blocks plain requests (403).** Use the Playwright path; if
  `playwright install chromium` was skipped, the script exits with install
  instructions. `--no-browser` only works when `matchdict.json` already
  exists in the data dir.
- **Coordinate spaces.** WhoScored events are 0-100 and scaled to a UEFA
  105x68 pitch (`x*1.05, y*0.68`) — the blueprint convention. Both teams
  attack toward x=105 in the raw data; the away team's axes are inverted
  for display and home shots are flipped in the shot map.
- **FotMob match id resolution needs the match date.** If the date endpoint
  returns nothing, pass `--fotmob-id` explicitly (from the FotMob URL `#<id>`).
- **Empty shot map = missing FotMob id.** Event panels still render; only
  shot/xG/momentum/GK panels degrade.
- **Player names in passing networks** come from WhoScored's
  `playerIdNameDictionary`; without `matchdict.json` only counts are shown.
- **Player-level panels need real names to match.** FotMob shot xG/xGOT
  match on `playerName` (fallback: `shortName`); if a player's name
  differs between sources, xG shows 0. Without `shots.csv` the individual
  shot map falls back to WhoScored events (positions but no xG).
- **Only players who touched the ball** appear in `player_stats.csv` and
  the per-player dashboards — bench/roster players with zero events are
  skipped by design.
- **Players with <3 touches** get a 0 `Total_Area_Covered` (convex hull
  guard) instead of crashing the heatmap.
- Be polite: scrape one match at a time; don't loop over hundreds of URLs.

## Verification

- `scrape_match.py` prints per-step status lines and a final
  `✅ Done in Xs. Bundle ready in ...`.
- `render_report.py` prints `✅ <path>` for both PNGs.
- Open `match_report_1.png`: every panel populated, black background, team
  colors consistent (home left, away right), shirt numbers legible inside
  nodes, xT momentum in the center row.
- Open `match_report_2.png`: all 12 zone panels populated with data.
- `uv run pytest` passes (offline, uses synthetic match data).
