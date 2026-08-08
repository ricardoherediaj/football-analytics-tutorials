"""Match statistics computed from the master event frame."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config


def _team_mask(df: pd.DataFrame, team: str) -> pd.Series:
    return df["teamName"] == team


def _count(df: pd.DataFrame, team: str, types=None, outcome=None, qualifiers=None) -> int:
    mask = _team_mask(df, team)
    if types:
        mask &= df["type"].isin(types)
    if outcome:
        mask &= df["outcomeType"] == outcome
    if qualifiers:
        mask &= df["qualifiers"].str.contains(qualifiers, na=False)
    return int(mask.sum())


def calculate_match_stats(df: pd.DataFrame, home: str, away: str) -> dict:
    """All headline stats for the match-stats bar chart (blueprint set)."""
    h, a = home, away

    # Possession (% of passes)
    h_passes = _count(df, h, types=["Pass"])
    a_passes = _count(df, a, types=["Pass"])
    total = h_passes + a_passes
    h_poss = round(h_passes / total * 100, 2) if total else 50.0
    a_poss = round(a_passes / total * 100, 2) if total else 50.0

    # Field tilt (touches in final third x>=70)
    h_tilt = int(df[(df["teamName"] == h) & (df["isTouch"] == 1) & (df["x"] >= 70)].shape[0])
    a_tilt = int(df[(df["teamName"] == a) & (df["isTouch"] == 1) & (df["x"] >= 70)].shape[0])
    tilt_total = h_tilt + a_tilt
    h_ft = round(h_tilt / tilt_total * 100, 2) if tilt_total else 50.0
    a_ft = round(a_tilt / tilt_total * 100, 2) if tilt_total else 50.0

    # Passes / accurate passes
    h_acc = _count(df, h, types=["Pass"], outcome="Successful")
    a_acc = _count(df, a, types=["Pass"], outcome="Successful")

    # Long balls (exclude corners/crosses)
    def longballs(team):
        m = (df["teamName"] == team) & (df["type"] == "Pass") & (
            df["qualifiers"].str.contains("Longball", na=False)
        ) & (~df["qualifiers"].str.contains("Corner|Cross", na=False))
        return int(m.sum())

    h_lb, a_lb = longballs(h), longballs(a)

    # Corners
    h_cor = _count(df, h, types=["CornerAwarded"])
    a_cor = _count(df, a, types=["CornerAwarded"])

    # Avg goalkeeper kick length
    def gk_kick_len(team):
        m = (df["teamName"] == team) & (df["type"] == "Pass") & (
            df["qualifiers"].str.contains("GoalkeeperThrow|GoalKick", na=False)
        ) & df["endX"].notna() & df["x"].notna()
        if m.sum() == 0:
            return 0.0
        return round(float(np.sqrt((df.loc[m, "endX"] - df.loc[m, "x"]) ** 2 + (df.loc[m, "endY"] - df.loc[m, "y"]) ** 2).mean()), 2)

    h_gk, a_gk = gk_kick_len(h), gk_kick_len(a)

    # Tackles won
    h_tkl = _count(df, h, types=["Tackle"], outcome="Successful")
    a_tkl = _count(df, a, types=["Tackle"], outcome="Successful")

    # Interceptions
    h_int = _count(df, h, types=["Interception"])
    a_int = _count(df, a, types=["Interception"])

    # Clearances
    h_clr = _count(df, h, types=["Clearance"])
    a_clr = _count(df, a, types=["Clearance"])

    # Aerials won
    h_arl = _count(df, h, types=["Aerial"], outcome="Successful")
    a_arl = _count(df, a, types=["Aerial"], outcome="Successful")

    # PPDA: opponent passes in own 60% / defensive actions in opponent 40%
    def ppda(def_team, opp_team):
        opp_passes = int(
            df[(df["teamName"] == opp_team) & (df["type"] == "Pass")
               & (df["outcomeType"] == "Successful") & (df["x"] < 63)].shape[0]
        )
        def_actions = int(
            df[(df["teamName"] == def_team)
               & df["type"].isin(["Interception", "Tackle", "Foul", "Challenge"])
               & (df["x"] > 42)].shape[0]
        )
        return round(opp_passes / def_actions, 2) if def_actions else None

    h_ppda, a_ppda = ppda(h, a), ppda(a, h)

    return {
        "Possession": {"home": h_poss, "away": a_poss},
        "Field Tilt": {"home": h_ft, "away": a_ft},
        "Passes (Acc.)": {"home": h_acc, "away": a_acc},
        "LongBalls (Acc.)": {"home": h_lb, "away": a_lb},
        "Corners": {"home": h_cor, "away": a_cor},
        "Avg. GK Kick Len.": {"home": h_gk, "away": a_gk},
        "Tackles (Wins)": {"home": h_tkl, "away": a_tkl},
        "Interceptions": {"home": h_int, "away": a_int},
        "Clearances": {"home": h_clr, "away": a_clr},
        "Aerials (Wins)": {"home": h_arl, "away": a_arl},
        "PPDA": {"home": h_ppda, "away": a_ppda},
    }


def total_xt(df: pd.DataFrame, home: str, away: str) -> dict:
    """Sum of positive xT per team (for the momentum chart text)."""
    out = {}
    for team in (home, away):
        team_xt = df[(df["teamName"] == team) & (df["xT"].notna())]["xT"]
        out[team] = round(float(team_xt.clip(lower=0).sum()), 2) if len(team_xt) else 0.0
    return out


def shot_stats_from_events(df: pd.DataFrame, home: str, away: str) -> dict:
    """Shot summary from WhoScored shot events (goals, shots, on target, big chances, avg dist)."""
    shots = df[df["type"].isin(config.SHOT_TYPES)].copy()
    out = {}
    for team in (home, away):
        team_shots = shots[shots["teamName"] == team]
        saved = team_shots[(team_shots["type"] == "SavedShot")].shape[0]
        goals = team_shots[(team_shots["type"] == "Goal") & (~team_shots["qualifiers"].str.contains("OwnGoal", na=False))].shape[0]
        big_chance = team_shots[team_shots["qualifiers"].str.contains("BigChance", na=False)].shape[0]
        big_miss = team_shots[
            (team_shots["qualifiers"].str.contains("BigChance", na=False))
            & (team_shots["type"] != "Goal")
        ].shape[0]
        dist = (
            np.sqrt((team_shots["x"] - 105) ** 2 + (team_shots["y"] - 34) ** 2).mean()
            if len(team_shots) else 0.0
        )
        out[team] = {
            "goals": goals,
            "shots": len(team_shots),
            "on_target": saved + goals,
            "big_chances": big_chance,
            "big_chances_missed": big_miss,
            "avg_distance": round(float(dist), 2),
            "xg": 0.0,
            "xgot": 0.0,
            "xg_per_shot": 0.0,
        }
    return out
