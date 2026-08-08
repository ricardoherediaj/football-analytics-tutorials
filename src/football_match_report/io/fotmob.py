"""FotMob API: match-id resolution, matchDetails (shots, momentum, colors, stats)."""

from __future__ import annotations

import re

import pandas as pd
import requests

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)
BASE = "https://www.fotmob.com/api/data"


def resolve_match_id(matchdict: dict, fotmob_id: int | None = None) -> int | None:
    """Resolve FotMob match id from the WhoScored date + team names."""
    if fotmob_id:
        return fotmob_id
    date_str = matchdict.get("startDate", "")[:10].replace("-", "")
    if not date_str:
        return None
    try:
        r = requests.get(
            f"{BASE}/matches", params={"date": date_str},
            headers={"User-Agent": UA}, timeout=20,
        )
        r.raise_for_status()
    except Exception:
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


def fetch_match_details(match_id: int) -> dict:
    r = requests.get(
        f"{BASE}/matchDetails",
        params={"matchId": match_id},
        headers={"User-Agent": UA, "Referer": "https://www.fotmob.com/"},
        timeout=25,
    )
    r.raise_for_status()
    return r.json()


def parse_fotmob_url(url: str) -> int | None:
    m = re.search(r"#(\d+)", url)
    if m:
        return int(m.group(1))
    m = re.search(r"/match(?:es)?/(\d+)", url)
    return int(m.group(1)) if m else None


def shots_to_df(fotmob: dict) -> pd.DataFrame:
    """Flatten the FotMob shot map into a DataFrame with xG and team ids."""
    shots = (fotmob.get("content") or {}).get("shotmap", {}).get("shots", [])
    df = pd.DataFrame(shots)
    if len(df):
        df["team_id"] = df["teamId"]
        df["is_big_chance"] = df.get("situation", pd.Series(dtype=str)).eq("BigChance")
        df["is_own_goal"] = df.get("isOwnGoal", False)
        for col in ("x", "y"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def team_colors(fotmob: dict) -> dict:
    """{fotmob_team_id: hex} from general.teamColors, shotmap fallback."""
    general = fotmob.get("general") or {}
    colors = {}
    tc = general.get("teamColors") or {}
    light = tc.get("lightMode") or {}
    home_id = (general.get("homeTeam") or {}).get("id")
    away_id = (general.get("awayTeam") or {}).get("id")
    if light.get("home") and home_id:
        colors[home_id] = light["home"]
    if light.get("away") and away_id:
        colors[away_id] = light["away"]
    if len(colors) == 2:
        return colors
    for s in (fotmob.get("content") or {}).get("shotmap", {}).get("shots", []):
        c = s.get("teamColor")
        if c:
            colors[s.get("teamId")] = c
    return colors


def momentum_series(fotmob: dict) -> list[dict]:
    data = (fotmob.get("content") or {}).get("momentum", {}).get("main", {}).get("data", [])
    return [{"minute": d.get("minute"), "value": d.get("value")} for d in data if "value" in d]


def match_facts(fotmob: dict) -> dict:
    mf = (fotmob.get("content") or {}).get("matchFacts", {})
    pom = mf.get("playerOfTheMatch") or {}
    if not pom:
        return {}
    return {
        "player_of_match": {
            "name": (pom.get("name") or {}).get("fullName") or pom.get("name"),
            "team": pom.get("teamName"),
            "rating": (pom.get("rating") or {}).get("num"),
        }
    }


def meta_from_fotmob(fotmob: dict, fm_id: int) -> dict:
    """Minimal meta (teams/colors/momentum/facts) from FotMob alone."""
    general = fotmob.get("general") or {}
    status = (fotmob.get("header") or {}).get("status") or {}
    home = general.get("homeTeam") or {}
    away = general.get("awayTeam") or {}
    score = None
    m = re.findall(r"\d+", str(status.get("scoreStr") or ""))
    if len(m) >= 2:
        score = {"home": int(m[0]), "away": int(m[1])}
    return {
        "match_id_fotmob": fm_id,
        "teams": {
            "home": {"name": home.get("name"), "who_scored_id": None, "fotmob_id": home.get("id")},
            "away": {"name": away.get("name"), "who_scored_id": None, "fotmob_id": away.get("id")},
        },
        "score": score,
        "ft_score": score,
        "start_date": (status.get("utcTime") or "")[:10],
        "competition": general.get("leagueName"),
        "colors": team_colors(fotmob),
        "momentum": momentum_series(fotmob),
        **match_facts(fotmob),
    }
