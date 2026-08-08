# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [2.0.0] — 2026-08-08

### Added
- `football_match_report` Python package (src layout, CLI entry points).
- Two 4x3 post-match team report figures (24 charts) following the
  Post-Match-Report-2.0 blueprint: passing networks (shirt-number nodes,
  line heights), shot map with xG stats bar, defensive blocks, goalkeeper
  saves, progressive passes/carries, xT momentum, match stats, final-third
  entries, box entries, Zone 14 & half-spaces, crosses, pass-end-zone
  heatmaps, high turnovers, chance-creating zones, congestion map.
- Automated data pipeline: WhoScored (Playwright) + FotMob
  (`/api/data/matchDetails`, auto-resolved match id, no token).
- Black theme, UEFA 105x68 pitch, circle=starter/square=sub convention.
- Installable agent skill at `skills/football-match-report/`.
- Offline test suite with synthetic match data; ruff linting; CI workflow.

### Changed
- Replaced the 2025 notebook workflow (manual Selenium, rotating FotMob
  `x-mas` token, hardcoded team ids) with two commands.
- WhoScored events scaled 0-100 → UEFA 105x68 (blueprint convention)
  instead of StatsBomb 120x80.

## [0.1.0] — 2025

- Original notebooks: `match_dashboard_template.ipynb`,
  `cwc_scraping_test.ipynb` (kept for reference).
