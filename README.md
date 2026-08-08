# football-analytics-tutorials

Professional post-match team reports from **WhoScored + FotMob** — a clean
Python package + an agent skill, built on the
[Post-Match-Report-2.0](https://github.com/adnaaan433/Post-Match-Report-2.0)
blueprint.

![Match report 1](docs/match_report_1_salzburg_rm.png)

## What it does

Given **any WhoScored match URL**, the pipeline:

1. **Scrapes WhoScored** (headless Chromium) → full event stream: passes,
   tackles, carries, recoveries with coordinates.
2. **Auto-resolves the FotMob match id** from the match date + team names →
   shots with xG/xGOT, native momentum, official stats, player of the
   match, real team colors.
3. **Renders two 4x3 report figures** (UEFA pitch, black background,
   blueprint styling): passing networks with shirt-number nodes, shot map,
   defensive blocks, goalkeeper saves, progressive passes/carries,
   xT momentum, match stats, final-third entries, box entries, Zone 14,
   crosses, pass-end zones, high turnovers, chance creation, congestion.

No API keys, no manual Selenium sessions, no rotating tokens, no hardcoded
team ids — works for any match (Club World Cup, Premier League, etc.).

## Quick start

```bash
# 1. Install (uv)
uv sync --extra scrape

# 2. One-time browser install (for WhoScored)
uv run playwright install chromium

# 3. Scrape any match (WhoScored + FotMob merged)
uv run football-match-report scrape \
  "https://www.whoscored.com/matches/1873310/live/international-fifa-club-world-cup-2025-salzburg-real-madrid" \
  --out ./data

# 4. Render the two report figures (offline)
uv run football-match-report render --data ./data --out ./report
```

Outputs: `report/match_report_1.png` (team report) +
`report/match_report_2.png` (zones report).

## Repository layout

```
src/football_match_report/     # the package
  core/events.py               # event pipeline: carries, possession, xT, UEFA scaling
  core/stats.py                # match/shot statistics
  io/whoscored.py              # Playwright scraper
  io/fotmob.py                 # FotMob API (id resolve, matchDetails)
  viz/pass_network.py          # passing networks (shirt numbers, line heights)
  viz/defensive_block.py       # defensive KDE heatmaps
  viz/progressive.py           # progressive passes & carries
  viz/shots.py                 # shot map + goalkeeper saves
  viz/momentum.py              # xT momentum chart
  viz/match_stats.py           # stats bars
  viz/zones.py                 # 8 advanced zone charts
  viz/report.py                # 2x 4x3 figure assembly
  cli.py                       # scrape + render commands
skills/football-match-report/  # installable agent skill (SKILL.md + thin wrappers)
tests/                         # offline unit + render tests (synthetic match data)
docs/                          # sample report images
```

## Install as an agent skill

```bash
mkdir -p ~/.hermes/skills
cp -R skills/football-match-report ~/.hermes/skills/
```

Then any agent session can load `football-match-report` by name. Usage,
metric definitions and pitfalls are in
[`skills/football-match-report/SKILL.md`](skills/football-match-report/SKILL.md)
and [`references/metrics.md`](skills/football-match-report/references/metrics.md).

## Development

```bash
uv run pytest          # offline tests (synthetic match data)
uv run ruff check src tests
```

## Credits & license

- Chart design follows [Post-Match-Report-2.0](https://github.com/adnaaan433/Post-Match-Report-2.0)
  by Adnan Ahmed (GPL-3.0) — rebuilt and reorganized here with permission
  of the original work's license terms.
- Original 2025 notebooks kept in `notebooks/` for reference.
- MIT — see [LICENSE](LICENSE). Data © WhoScored and FotMob; for
  personal/educational use, respect each site's terms and rate limits
  (one match at a time).
