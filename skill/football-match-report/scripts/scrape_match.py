#!/usr/bin/env python3
"""
scrape_match.py — one-command match data pipeline for the football-match-report skill.

Takes ANY WhoScored match URL and produces a self-contained data bundle that
render_report.py turns into a match report. The pipeline merges two sources:

* WhoScored — full event stream (passes, tackles, carries) via headless
  Chromium (the page is bot-walled). MatchCentreData JSON is embedded in the
  page scripts.
* FotMob — shots with xG, momentum, stats, team colors via the public
  /api/data/matchDetails endpoint (no token needed since 2025). The FotMob
  match id is auto-resolved from the WhoScored match date + team names.

Bundle layout (consumed by render_report.py):

    out/
    ├── matchdict.json          # raw WhoScored matchCentreData (WhoScored mode)
    ├── events.csv              # flattened, snake_case event stream
    ├── shots.csv               # FotMob shot map with xG
    ├── meta.json               # teams, ids, score, venue, colors, momentum, stats
    └── xt_grid.csv             # expected-threat grid (12x8) used for momentum/xT

Usage
-----
    python scrape_match.py "<whoscored-match-url>" [--out DIR] [--fotmob-id ID] [--no-browser]
    python scrape_match.py --fotmob-id <id> [--out DIR]     # FotMob-only reduced bundle

Examples
--------
    python scrape_match.py "https://www.whoscored.com/matches/1873310/live/international-fifa-club-world-cup-2025-salzburg-real-madrid"
    python scrape_match.py "https://www.whoscored.com/matches/1873310/live/..." --fotmob-id 4685754
    python scrape_match.py "..." --out ./data 2>&1 | tee scrape.log
    python scrape_match.py --fotmob-id 4685754 --out ./data   # shots/xG/momentum only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)
FOTMOB_BASE = "https://www.fotmob.com/api/data"

# WhoScored coordinate space is 0-100 (both axes); StatsBomb is 120x80.
X_SCALE, Y_SCALE = 1.2, 0.8


# --------------------------------------------------------------------------- #
# WhoScored: Playwright fetch + matchCentreData extraction
# --------------------------------------------------------------------------- #
def fetch_whoscored_match(url: str, headless: bool = True) -> dict:
    """Load a WhoScored match page in headless Chromium and return matchCentreData."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "Playwright is required to fetch WhoScored. Install with:\n"
            "  uv pip install playwright && playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=UA)
        page.goto(url, timeout=60_000, wait_until="domcontentloaded")
        # Give the anti-bot challenge + JS a chance to settle and inject data.
        page.wait_for_timeout(8_000)
        html = page.content()
        browser.close()

    data = _extract_match_centredata(html)
    if data is None:
        sys.exit("Could not find matchCentreData on the WhoScored page. The match may not exist or the page layout changed.")
    return data


def _extract_match_centredata(html: str) -> dict | None:
    """Pull the matchCentreData JSON blob out of the WhoScored page source."""
    patterns = [
        re.compile(r"matchCentreData:\s*(\{.*?\})\s*,\s*[\"']matchCentreEventTypeJson", re.S),
        re.compile(r"matchCentreData:\s*(\{.*?\})\s*\},\s*[\"']matchCentrePeriodJson", re.S),
    ]
    for pat in patterns:
        m = pat.search(html)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue

    # Fallback: balanced-brace scan from the marker onward.
    idx = html.find("matchCentreData:")
    if idx == -1:
        return None
    start = html.find("{", idx)
    depth, i = 0, start
    while i < len(html):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    try:
        return json.loads(html[start : i + 1])
    except json.JSONDecodeError:
        return None


def flatten_events(matchdict: dict) -> pd.DataFrame:
    """Flatten WhoScored events into a snake_case DataFrame with display names."""
    events = matchdict.get("events", [])
    df = pd.DataFrame(events)

    def display(x):
        return x.get("displayName") if isinstance(x, dict) else None

    df["type_display_name"] = df["type"].apply(display)
    df["outcome_type_display_name"] = df["outcomeType"].apply(display)
    df["period_display_name"] = df["period"].apply(display)

    # Standardize column names (WhoScored camelCase -> snake_case)
    rename = {
        "eventId": "event_id",
        "playerId": "player_id",
        "teamId": "team_id",
        "expandedMinute": "expanded_minute",
        "isTouch": "is_touch",
        "endX": "end_x",
        "endY": "end_y",
        "blockedX": "blocked_x",
        "blockedY": "blocked_y",
        "goalMouthZ": "goal_mouth_z",
        "goalMouthY": "goal_mouth_y",
        "relatedEventId": "related_event_id",
        "relatedPlayerId": "related_player_id",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    # Coordinates: WhoScored 0-100 -> StatsBomb 120x80
    for col in ("x", "y", "end_x", "end_y"):
        if col in df.columns:
            df[col] = df[col].astype(float) * (X_SCALE if col in ("x", "end_x") else Y_SCALE)

    # Convenience flags
    df["is_shot"] = df["type_display_name"].isin(["Shot", "SavedShot", "MissedShots", "Goal"])
    df["is_goal"] = df["type_display_name"].isin(["Goal"]) & (df["outcome_type_display_name"] == "Successful")

    # qualifiers stays a list of dicts in CSV as JSON string for later parsing
    if "qualifiers" in df.columns:
        df["qualifiers"] = df["qualifiers"].apply(lambda q: json.dumps(q) if isinstance(q, list) else None)

    return df


# --------------------------------------------------------------------------- #
# FotMob: match-id resolution + matchDetails fetch (plain requests)
# --------------------------------------------------------------------------- #
def resolve_fotmob_match_id(matchdict: dict, fotmob_id: int | None = None) -> int | None:
    """Resolve the FotMob match id from the WhoScored date + team names."""
    if fotmob_id:
        return fotmob_id

    date_str = matchdict.get("startDate", "")[:10]  # 2025-06-27
    if not date_str:
        return None
    date_compact = date_str.replace("-", "")

    try:
        r = requests.get(
            f"{FOTMOB_BASE}/matches", params={"date": date_compact},
            headers={"User-Agent": UA}, timeout=20,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"[fotmob] match-id resolution failed ({e}); pass --fotmob-id to skip")
        return None

    home = (matchdict.get("home") or {}).get("name", "").lower()
    away = (matchdict.get("away") or {}).get("name", "").lower()

    for league in r.json().get("leagues", []):
        for m in league.get("matches") or []:
            h = (m.get("home") or {}).get("name", "").lower()
            a = (m.get("away") or {}).get("name", "").lower()
            if home in (h, a) and away in (h, a):
                return m.get("id")
    return None


def fetch_fotmob(match_id: int) -> dict:
    """Fetch FotMob matchDetails (shots, stats, momentum, team colors)."""
    r = requests.get(
        f"{FOTMOB_BASE}/matchDetails",
        params={"matchId": match_id},
        headers={"User-Agent": UA, "Referer": "https://www.fotmob.com/"},
        timeout=25,
    )
    r.raise_for_status()
    return r.json()


def shots_to_df(fotmob: dict) -> pd.DataFrame:
    """Extract the shot map from FotMob matchDetails."""
    shots = (fotmob.get("content") or {}).get("shotmap", {}).get("shots", [])
    df = pd.DataFrame(shots)
    if len(df):
        df["is_big_chance"] = df.get("situation", pd.Series(dtype=str)).eq("BigChance")
        df["is_own_goal"] = df.get("isOwnGoal", False)
        df["team_id"] = df["teamId"]
        df["x"] = pd.to_numeric(df["x"], errors="coerce")
        df["y"] = pd.to_numeric(df["y"], errors="coerce")
    return df


# --------------------------------------------------------------------------- #
# Output bundle
# --------------------------------------------------------------------------- #
def build_meta(matchdict: dict, fotmob: dict | None, fotmob_id: int | None) -> dict:
    """Assemble teams, score, venue and (when available) FotMob colors/stats/momentum."""
    home, away = matchdict.get("home", {}), matchdict.get("away", {})
    meta = {
        "source_url": None,
        "match_id_fotmob": fotmob_id,
        "teams": {
            "home": {"name": home.get("name"), "who_scored_id": home.get("teamId")},
            "away": {"name": away.get("name"), "who_scored_id": away.get("teamId")},
        },
        "score": matchdict.get("score"),
        "ft_score": matchdict.get("ftScore"),
        "ht_score": matchdict.get("htScore"),
        "start_date": matchdict.get("startDate"),
        "venue": matchdict.get("venueName"),
        "attendance": matchdict.get("attendance"),
        "referee": matchdict.get("referee"),
        "competition": matchdict.get("tournamentName") or matchdict.get("competitionName"),
    }

    if fotmob:
        general = fotmob.get("general") or {}
        content = fotmob.get("content") or {}
        meta["teams"]["home"]["fotmob_id"] = (general.get("homeTeam") or {}).get("id")
        meta["teams"]["away"]["fotmob_id"] = (general.get("awayTeam") or {}).get("id")
        meta["competition"] = meta["competition"] or general.get("leagueName") or general.get("parentLeagueName")
        meta["colors"] = _extract_colors(fotmob)
        meta["momentum"] = _extract_momentum(fotmob)
        meta["stats"] = _extract_stats(fotmob)
        meta["player_of_match"] = _extract_pom(fotmob)
    return meta


def _extract_colors(fotmob: dict) -> dict:
    """Team colors from FotMob (general.teamColors preferred, shotmap fallback)."""
    general = fotmob.get("general") or {}
    colors = {}

    # Preferred: explicit teamColors block (light mode = kit colors on white)
    tc = general.get("teamColors") or {}
    light = tc.get("lightMode") or {}
    if light.get("home") and light.get("away"):
        home_id = (general.get("homeTeam") or {}).get("id")
        away_id = (general.get("awayTeam") or {}).get("id")
        if home_id:
            colors[home_id] = light["home"]
        if away_id:
            colors[away_id] = light["away"]
        if len(colors) == 2:
            return colors

    # Fallback: shotmap teamColor per shot
    shots = (fotmob.get("content") or {}).get("shotmap", {}).get("shots", [])
    for s in shots:
        c = s.get("teamColor")
        if c:
            colors[s.get("teamId")] = c
    return colors


def _extract_momentum(fotmob: dict) -> list:
    """Native FotMob momentum series: [{minute, value}, ...] (positive = home)."""
    data = (fotmob.get("content") or {}).get("momentum", {}).get("main", {}).get("data", [])
    return [{"minute": d.get("minute"), "value": d.get("value")} for d in data if "value" in d]


def _extract_stats(fotmob: dict) -> dict:
    """Top stats per period from FotMob (possession, xG, shots, ...)."""
    periods = (fotmob.get("content") or {}).get("stats", {}).get("Periods", {})
    out = {}
    for period, block in periods.items():
        top = {}
        for group in block.get("stats", []):
            for stat in group.get("stats", []):
                key = stat.get("key")
                if key:
                    top[key] = {"title": stat.get("title"), "values": stat.get("stats")}
        out[period] = top
    return out


def _extract_pom(fotmob: dict) -> dict | None:
    mf = (fotmob.get("content") or {}).get("matchFacts", {})
    pom = mf.get("playerOfTheMatch") or {}
    if not pom:
        return None
    return {
        "name": ((pom.get("name") or {}).get("fullName") or pom.get("name")),
        "team": pom.get("teamName"),
        "rating": (pom.get("rating") or {}).get("num"),
    }


def xt_grid_default() -> pd.DataFrame:
    """Standard 12x8 expected-threat grid (Karun Singh / xT framework)."""
    grid_path = Path(__file__).resolve().parent.parent / "data" / "xt_grid.csv"
    return pd.read_csv(grid_path, header=None)


# --------------------------------------------------------------------------- #
# FotMob-only mode (no WhoScored / no browser)
# --------------------------------------------------------------------------- #
def parse_fotmob_url(url: str) -> int | None:
    """Extract a FotMob match id from a URL like .../matches/.../2vib2u#4685754."""
    m = re.search(r"#(\d+)", url)
    if m:
        return int(m.group(1))
    m = re.search(r"/match(?:es)?/(\d+)", url)
    if m:
        return int(m.group(1))
    return None


def build_meta_fotmob_only(fotmob: dict, fm_id: int, source_url: str) -> dict:
    """Meta bundle from FotMob alone (used when no WhoScored data is available)."""
    general = fotmob.get("general") or {}
    status = (fotmob.get("header") or {}).get("status") or {}
    home = general.get("homeTeam") or {}
    away = general.get("awayTeam") or {}

    colors = {}
    tc = general.get("teamColors") or {}
    light = tc.get("lightMode") or {}
    if light.get("home"):
        colors[home.get("id")] = light["home"]
    if light.get("away"):
        colors[away.get("id")] = light["away"]

    meta = {
        "source_url": source_url,
        "match_id_fotmob": fm_id,
        "teams": {
            "home": {"name": home.get("name"), "who_scored_id": None, "fotmob_id": home.get("id")},
            "away": {"name": away.get("name"), "who_scored_id": None, "fotmob_id": away.get("id")},
        },
        "score": parse_score_str(status.get("scoreStr")),
        "ft_score": parse_score_str(status.get("scoreStr")),
        "start_date": (status.get("utcTime") or "")[:10],
        "venue": None,
        "attendance": None,
        "referee": None,
        "competition": general.get("leagueName"),
        "colors": colors,
        "momentum": _extract_momentum(fotmob),
        "stats": _extract_stats(fotmob),
        "player_of_match": _extract_pom(fotmob),
        "data_sources": ["fotmob"],
    }
    return meta


def parse_score_str(raw) -> dict | None:
    """Parse '0 - 3' / '1 : 2' style score strings into {'home': 0, 'away': 3}."""
    if not raw:
        return None
    m = re.findall(r"\d+", str(raw))
    return {"home": int(m[0]), "away": int(m[1])} if len(m) >= 2 else None


def empty_events_schema() -> pd.DataFrame:
    """Empty events frame with the columns render_report expects."""
    return pd.DataFrame(columns=[
        "event_id", "minute", "second", "team_id", "x", "y", "end_x", "end_y",
        "player_id", "is_touch", "type_display_name", "outcome_type_display_name",
        "period_display_name", "qualifiers",
    ])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?", help="WhoScored match URL (https://www.whoscored.com/matches/ID/live/...) "
                                           "or FotMob match URL (https://www.fotmob.com/matches/.../...#ID)")
    ap.add_argument("--out", default="data", help="output directory (default: ./data)")
    ap.add_argument("--fotmob-id", type=int, default=None, help="FotMob match id (auto-resolved if omitted; "
                                                                "required if no URL is given)")
    ap.add_argument("--no-browser", action="store_true", help="skip WhoScored fetch (use existing data/matchdict.json)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    fm_id = args.fotmob_id

    # --- FotMob-only mode: a FotMob URL or --fotmob-id with no WhoScored URL.
    if fm_id or (args.url and "fotmob.com" in args.url):
        if args.url and "fotmob.com" in args.url:
            fm_id = fm_id or parse_fotmob_url(args.url)
        if not fm_id:
            ap.error("could not find a match id in the FotMob URL (use ...#123456 or --fotmob-id)")
        print(f"[fotmob] using FotMob match id {fm_id} (no WhoScored — event panels will be limited)")
        fotmob = fetch_fotmob(fm_id)
        shots = shots_to_df(fotmob)
        shots.to_csv(out / "shots.csv", index=False)
        empty_events_schema().to_csv(out / "events.csv", index=False)
        xt_grid_default().to_csv(out / "xt_grid.csv", index=False, header=False)
        meta = build_meta_fotmob_only(fotmob, fm_id, args.url or f"https://www.fotmob.com/matches/...#{fm_id}")
        (out / "meta.json").write_text(json.dumps(meta, indent=2))
        print(f"[fotmob] {len(shots)} shots with xG -> {out / 'shots.csv'}")
        print(f"\n✅ Done in {time.time() - t0:.1f}s. FotMob-only bundle ready in {out}/")
        print("   Next:  python render_report.py --data {} --out report".format(out))
        return

    if not args.url:
        ap.error("provide a WhoScored URL, a FotMob URL, or --fotmob-id")

    # --- WhoScored path (with optional FotMob enrichment) ---
    if args.no_browser and (out / "matchdict.json").exists():
        print("[whoScored] reusing cached matchdict.json (--no-browser)")
        matchdict = json.loads((out / "matchdict.json").read_text())
    else:
        if not args.url or "whoscored.com" not in args.url:
            ap.error("a WhoScored URL is required for the event stream (or pass --fotmob-id for a FotMob-only bundle)")
        print("[whoScored] fetching match page with headless Chromium ...")
        matchdict = fetch_whoscored_match(args.url)
        (out / "matchdict.json").write_text(json.dumps(matchdict))
        print(f"[whoScored] matchCentreData OK ({len(matchdict.get('events', []))} events)")

    # Events
    df_events = flatten_events(matchdict)
    df_events.to_csv(out / "events.csv", index=False)
    print(f"[events] {len(df_events)} rows -> {out / 'events.csv'}")

    # FotMob
    if fm_id is None:
        fm_id = resolve_fotmob_match_id(matchdict)
    fotmob = None
    if fm_id:
        print(f"[fotmob] resolved match id {fm_id}, fetching matchDetails ...")
        fotmob = fetch_fotmob(fm_id)
        shots = shots_to_df(fotmob)
        shots.to_csv(out / "shots.csv", index=False)
        print(f"[fotmob] {len(shots)} shots with xG -> {out / 'shots.csv'}")
    else:
        print("[fotmob] no match id — shots/xG/momentum will be missing from the report")

    # xT grid
    xt = xt_grid_default()
    xt.to_csv(out / "xt_grid.csv", index=False, header=False)

    meta = build_meta(matchdict, fotmob, fm_id)
    meta["source_url"] = args.url
    meta["data_sources"] = ["whoScored"] + (["fotmob"] if fotmob else [])
    (out / "meta.json").write_text(json.dumps(meta, indent=2))

    print(f"\n✅ Done in {time.time() - t0:.1f}s. Bundle ready in {out}/")
    print("   Next:  python render_report.py --data {} --out report".format(out))


if __name__ == "__main__":
    main()
