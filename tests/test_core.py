"""Core pipeline tests: flattening, carries, xT, possession chains, stats."""

import numpy as np
import pandas as pd

from football_match_report import config
from football_match_report.core import events as core_events
from football_match_report.core import stats as core_stats


def test_flatten_events_columns(synthetic_matchdict):
    df = core_events.flatten_events(synthetic_matchdict)
    assert "type" in df.columns
    assert df["type"].isin(["Pass", "Goal"]).any()
    assert "cumulative_mins" in df.columns
    assert df["cumulative_mins"].isna().sum() == 0


def test_carries_synthesized():
    """A carry is synthesized between two same-team touches within a short window."""
    events = pd.DataFrame([
        {"eventId": 1, "minute": 10, "second": 0, "expandedMinute": 10, "period": 1,
         "teamId": 1, "playerId": 11, "type": "Pass", "outcomeType": "Successful",
         "x": 50, "y": 50, "endX": 65, "endY": 55, "isTouch": True,
         "qualifiers": "[]", "cumulative_mins": 10.0},
        # gap between event 1's end (65,55) and event 2's start (70,50) -> a dribble
        {"eventId": 2, "minute": 10, "second": 3, "expandedMinute": 10, "period": 1,
         "teamId": 1, "playerId": 11, "type": "Pass", "outcomeType": "Successful",
         "x": 70, "y": 50, "endX": 80, "endY": 45, "isTouch": True,
         "qualifiers": "[]", "cumulative_mins": 10.05},
        {"eventId": 3, "minute": 10, "second": 30, "expandedMinute": 10, "period": 1,
         "teamId": 2, "playerId": 21, "type": "Pass", "outcomeType": "Successful",
         "x": 40, "y": 40, "endX": 30, "endY": 35, "isTouch": True,
         "qualifiers": "[]", "cumulative_mins": 10.5},
    ])
    with_carries = core_events.insert_ball_carries(events)
    assert "Carry" in with_carries["type"].values
    carry = with_carries[with_carries["type"] == "Carry"]
    dx = carry["endX"] - carry["x"]
    dy = carry["endY"] - carry["y"]
    assert (np.sqrt(dx**2 + dy**2) >= 3.0).all()


def test_xt_assignment(synthetic_matchdict):
    xt = core_events.load_xt_grid("src/football_match_report/data/xt_grid.csv")
    df = core_events.build_master_df(synthetic_matchdict, xt)
    assert "xT" in df.columns
    assert df["xT"].notna().sum() > 0
    # xT of a successful pass can be positive or negative but finite
    assert np.isfinite(df["xT"].dropna()).all()


def test_uefa_scaling(synthetic_matchdict):
    xt = core_events.load_xt_grid("src/football_match_report/data/xt_grid.csv")
    df = core_events.build_master_df(synthetic_matchdict, xt)
    assert df["x"].max() <= 105.5
    assert df["y"].max() <= 68.5
    assert df["x"].min() >= 0
    assert df["y"].min() >= 0


def test_possession_chains(synthetic_matchdict):
    xt = core_events.load_xt_grid("src/football_match_report/data/xt_grid.csv")
    df = core_events.build_master_df(synthetic_matchdict, xt)
    assert "possession_id" in df.columns
    assert df["possession_id"].notna().all()
    assert df["possession_team"].notna().all()


def test_progressive_pass_filter(synthetic_matchdict):
    xt = core_events.load_xt_grid("src/football_match_report/data/xt_grid.csv")
    df = core_events.build_master_df(synthetic_matchdict, xt)
    home = synthetic_matchdict["home"]["name"]
    prog = df[(df["teamName"] == home) & (df["prog_pass"] >= 9.11)]
    # the home team has an assist pass ending at x=102 -> definitely progressive
    assert len(prog) >= 1


def test_match_stats_structure(synthetic_matchdict):
    xt = core_events.load_xt_grid("src/football_match_report/data/xt_grid.csv")
    df = core_events.build_master_df(synthetic_matchdict, xt)
    home = synthetic_matchdict["home"]["name"]
    away = synthetic_matchdict["away"]["name"]
    stats = core_stats.calculate_match_stats(df, home, away)
    assert "Possession" in stats
    assert abs(stats["Possession"]["home"] + stats["Possession"]["away"] - 100) < 1
    assert "PPDA" in stats
    assert "Field Tilt" in stats


def test_shot_stats(synthetic_matchdict):
    xt = core_events.load_xt_grid("src/football_match_report/data/xt_grid.csv")
    df = core_events.build_master_df(synthetic_matchdict, xt)
    home = synthetic_matchdict["home"]["name"]
    away = synthetic_matchdict["away"]["name"]
    stats = core_stats.shot_stats_from_events(df, home, away)
    # home scored 1 goal (big chance), away scored 1
    assert stats[home]["goals"] == 1
    assert stats[away]["goals"] == 1
    assert stats[home]["shots"] == 2
    assert stats[away]["shots"] == 3


# --- Regression tests: fix/visual-polish (v2.1.0) ---

def test_subs_get_is_first_eleven_false(synthetic_matchdict):
    """Subs arrive from WhoScored without isFirstEleven (NaN) -> must be False,
    so chart markers render as squares, not circles."""
    xt = core_events.load_xt_grid("src/football_match_report/data/xt_grid.csv")
    df = core_events.build_master_df(synthetic_matchdict, xt)
    assert df["isFirstEleven"].isna().sum() == 0, "no NaN may survive the merge"
    assert df["isFirstEleven"].dtype == bool
    # the subbed-in players (id +4) must be flagged False
    sub_rows = df[df["playerId"].isin([1104, 1204])]
    assert len(sub_rows) >= 1
    assert sub_rows["isFirstEleven"].sum() == 0
    # starters remain True
    starter_rows = df[df["playerId"].isin([1100, 1200])]
    assert starter_rows["isFirstEleven"].sum() == len(starter_rows)


def test_goal_mouth_coords_not_pitch_scaled(synthetic_matchdict):
    """goalMouthY/Z are 0-100 goal-mouth percentages, NOT pitch coordinates —
    they must survive build_master_df unscaled (previously *0.68 collapsed
    every shot into one column of the goal view)."""
    xt = core_events.load_xt_grid("src/football_match_report/data/xt_grid.csv")
    df = core_events.build_master_df(synthetic_matchdict, xt)
    shots = df[df["type"].isin(config.SHOT_TYPES) & df["goalMouthY"].notna()]
    assert len(shots) >= 1
    # fixture uses goalMouthY=40.0 -> must stay 40.0, not 40*0.68=27.2
    assert (shots["goalMouthY"] == 40.0).sum() == len(shots)
    assert (shots["goalMouthZ"] == 20.0).sum() == len(shots)
    # and they map across the full goal mouth (7.5..97.5), not one column
    gx = 7.5 + np.clip(shots["goalMouthY"].astype(float) / 100, 0, 1) * 90
    assert (gx == 43.5).sum() == len(shots)  # 40% -> 43.5 (dead center-ish)
