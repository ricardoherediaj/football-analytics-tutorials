"""Per-player statistics: leaderboards and individual stat dictionaries.

Pure data functions (no plotting) ported from the Post-Match-Report-2.0
blueprint's "Player Stats Counting" / "Top Players Dashboard" sections.
Every function works on the master event frame produced by
``core.events.build_master_df`` (UEFA 105x68 coordinates, JSON-string
``qualifiers``, numeric ``period``, boolean ``isFirstEleven``).

Naming convention follows the blueprint so the merged wide table
(``player_stats_table``) keeps recognizable column names.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull, QhullError

from .. import config
from . import events as core_events

# --------------------------------------------------------------------------- #
# Small shared helpers
# --------------------------------------------------------------------------- #

def _player_names(df: pd.DataFrame) -> list[str]:
    """Unique non-empty player names in the frame."""
    return [n for n in df["name"].dropna().unique() if isinstance(n, str) and n]


def _short_name_series(names: pd.Series) -> pd.Series:
    return names.map(core_events.short_name)


def _finish_leaderboard(rows: list[dict], top: int) -> pd.DataFrame:
    """rows -> DataFrame with total, sorted desc, top-N, shortName column."""
    if not rows:
        cols = ["name", "shortName", "total"]
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(rows)
    out["total"] = out.select_dtypes(include=[np.number]).sum(axis=1)
    out = out.sort_values("total", ascending=False).head(top).reset_index(drop=True)
    out["shortName"] = _short_name_series(out["name"])
    return out


# --------------------------------------------------------------------------- #
# Top-players leaderboards (dashboard panels + bar charts)
# --------------------------------------------------------------------------- #

def top_progressors(df: pd.DataFrame, team: str | None = None, top: int = 5) -> pd.DataFrame:
    """Progressive passes + progressive carries + line-breaking (through) passes."""
    d = df if team is None else df[df["teamName"] == team]
    open_play = ~d["qualifiers"].str.contains("CornerTaken|Freekick", na=False)
    rows = []
    for name in _player_names(d):
        prog_pass = len(d[
            (d["name"] == name) & (d["prog_pass"] >= config.PROGRESSIVE_DIST)
            & (d["x"] >= config.PROGRESSIVE_START_X)
            & (d["outcomeType"] == "Successful") & open_play
        ])
        prog_carry = len(d[
            (d["name"] == name) & (d["prog_carry"] >= config.PROGRESSIVE_DIST)
            & (d["endX"] >= config.PROGRESSIVE_START_X)
        ])
        lb_pass = len(d[
            (d["name"] == name) & (d["type"] == "Pass")
            & (d["qualifiers"].str.contains("Throughball", na=False))
        ])
        rows.append({"name": name, "Progressive Passes": prog_pass,
                     "Progressive Carries": prog_carry, "LineBreaking Pass": lb_pass})
    return _finish_leaderboard(rows, top)


def top_threat(df: pd.DataFrame, team: str | None = None, top: int = 5) -> pd.DataFrame:
    """xT created by passing + xT created by carrying."""
    d = df if team is None else df[df["teamName"] == team]
    open_play = ~d["qualifiers"].str.contains("CornerTaken|Freekick|ThrowIn", na=False)
    rows = []
    for name in _player_names(d):
        xt_pass = d[
            (d["name"] == name) & (d["type"] == "Pass") & (d["xT"] >= 0)
            & (d["outcomeType"] == "Successful") & open_play
        ]["xT"].sum()
        xt_carry = d[(d["name"] == name) & (d["type"] == "Carry") & (d["xT"] >= 0)]["xT"].sum()
        rows.append({"name": name, "xT from Pass": round(xt_pass, 2),
                     "xT from Carry": round(xt_carry, 2)})
    return _finish_leaderboard(rows, top)


def top_shot_sequence(df: pd.DataFrame, team: str | None = None, top: int = 5) -> pd.DataFrame:
    """Shots + shot assists (key passes) + buildup passes before a key pass."""
    d = df if team is None else df[df["teamName"] == team]
    no_carry = d[d["type"] != "Carry"].reset_index(drop=True)
    rows = []
    for name in _player_names(d):
        shots = len(d[(d["name"] == name) & (d["type"].isin(config.SHOT_TYPES))])
        shot_assist = len(d[
            (d["name"] == name) & (d["type"] == "Pass")
            & (d["qualifiers"].str.contains("KeyPass", na=False))
        ])
        buildup = len(no_carry[
            (no_carry["name"] == name) & (no_carry["type"] == "Pass")
            & (no_carry["qualifiers"].shift(-1).str.contains("KeyPass", na=False))
        ])
        rows.append({"name": name, "Shots": shots, "Shot Assist": shot_assist,
                     "Buildup to shot": buildup})
    return _finish_leaderboard(rows, top)


def top_defenders(df: pd.DataFrame, team: str | None = None, top: int = 5) -> pd.DataFrame:
    """Tackles (won) + interceptions + clearances."""
    d = df if team is None else df[df["teamName"] == team]
    rows = []
    for name in _player_names(d):
        tackles = len(d[
            (d["name"] == name) & (d["type"] == "Tackle") & (d["outcomeType"] == "Successful")
        ])
        interceptions = len(d[(d["name"] == name) & (d["type"] == "Interception")])
        clearances = len(d[(d["name"] == name) & (d["type"] == "Clearance")])
        rows.append({"name": name, "Tackles": tackles, "Interceptions": interceptions,
                     "Clearance": clearances})
    return _finish_leaderboard(rows, top)


# --------------------------------------------------------------------------- #
# Individual player stats (one dict per player per facet)
# --------------------------------------------------------------------------- #

def _passes_for(df: pd.DataFrame, pname: str) -> pd.DataFrame:
    return df[(df["type"] == "Pass") & (df["name"] == pname)]


def passing_stats(df: pd.DataFrame, pname: str) -> dict:
    d = _passes_for(df, pname)
    acc = d[d["outcomeType"] == "Successful"]
    inacc = d[d["outcomeType"] == "Unsuccessful"]
    accuracy = round(len(acc) / len(d) * 100, 2) if len(d) else 0.0

    open_play = ~d["qualifiers"].str.contains("CornerTaken|Freekick", na=False)
    prog = acc[(acc["prog_pass"] >= config.PROGRESSIVE_DIST) & (acc["x"] >= config.PROGRESSIVE_START_X) & open_play]
    through = d[d["qualifiers"].str.contains("Throughball", na=False) & open_play]
    longball = d[d["qualifiers"].str.contains("Longball", na=False) & open_play]
    crosses = d[d["qualifiers"].str.contains("Cross", na=False) & open_play]
    key = d[d["qualifiers"].str.contains("KeyPass", na=False)]
    big_created = d[d["qualifiers"].str.contains("BigChanceCreated", na=False)]
    assists = d[d["qualifiers"].str.contains("IntentionalGoalAssist", na=False)]

    no_carry = df[df["type"] != "Carry"].reset_index(drop=True)
    pre_assist = no_carry[
        (no_carry["name"] == pname) & (no_carry["type"] == "Pass")
        & (no_carry["outcomeType"] == "Successful")
        & (no_carry["qualifiers"].shift(-1).str.contains("IntentionalGoalAssist", na=False))
    ]
    shot_buildup = no_carry[
        (no_carry["name"] == pname) & (no_carry["type"] == "Pass")
        & (no_carry["outcomeType"] == "Successful")
        & (no_carry["qualifiers"].shift(-1).str.contains("KeyPass", na=False))
    ]

    final_third = acc[(acc["endX"] >= config.FINAL_THIRD_X) & open_play]
    pen_box = acc[
        (acc["endX"] >= config.BOX_X) & (acc["endY"] >= config.BOX_Y_MIN)
        & (acc["endY"] <= config.BOX_Y_MAX) & open_play
    ]

    ang = d["pass_or_carry_angle"]
    forward = d[(ang >= -85) & (ang <= 85) & open_play]
    side = d[((ang >= 85) & (ang <= 95)) | ((ang >= -95) & (ang <= -85)) & open_play]
    back = d[((ang >= 95) & (ang <= 180)) | ((ang >= -180) & (ang <= -95)) & open_play]

    corners = d[d["qualifiers"].str.contains("CornerTaken", na=False)]
    freekicks = d[d["qualifiers"].str.contains("Freekick", na=False)]
    throwins = d[d["qualifiers"].str.contains("ThrowIn", na=False)]

    return {
        "Name": pname,
        "Total_Passes": len(d),
        "Accurate_Passes": len(acc),
        "Miss_Pass": len(inacc),
        "Passing_Accuracy": accuracy,
        "Progressive_Passes": len(prog),
        "Chances_Created": len(key),
        "Big_Chances_Created": len(big_created),
        "Assists": len(assists),
        "Pre-Assists": len(pre_assist),
        "Buil-up_to_Shot": len(shot_buildup),
        "Final_Third_Passes": len(final_third),
        "Passes_In_Penalty_Box": len(pen_box),
        "Through_Pass_Attempts": len(through),
        "Accurate_Through_Passes": len(through[through["outcomeType"] == "Successful"]),
        "Crosses_Attempts": len(crosses),
        "Accurate_Crosses": len(crosses[crosses["outcomeType"] == "Successful"]),
        "Longballs_Attempts": len(longball),
        "Accurate_Longballs": len(longball[longball["outcomeType"] == "Successful"]),
        "Corners_Taken": len(corners),
        "Accurate_Corners": len(corners[corners["outcomeType"] == "Successful"]),
        "Freekicks_Taken": len(freekicks),
        "Accurate_Freekicks": len(freekicks[freekicks["outcomeType"] == "Successful"]),
        "ThrowIns_Taken": len(throwins),
        "Accurate_ThrowIns": len(throwins[throwins["outcomeType"] == "Successful"]),
        "Forward_Pass_Attempts": len(forward),
        "Accurate_Forward_Pass": len(forward[forward["outcomeType"] == "Successful"]),
        "Side_Pass_Attempts": len(side),
        "Accurate_Side_Pass": len(side[side["outcomeType"] == "Successful"]),
        "Back_Pass_Attempts": len(back),
        "Accurate_Back_Pass": len(back[back["outcomeType"] == "Successful"]),
        "xT_Increased_From_Pass": round(d[d["xT"] > 0]["xT"].sum(), 2),
        "xT_Decreased_From_Pass": round(d[d["xT"] < 0]["xT"].sum(), 2),
        "Total_xT_From_Pass": round(d["xT"].sum(), 2),
    }


def carrying_stats(df: pd.DataFrame, pname: str) -> dict:
    d = df[(df["type"] == "Carry") & (df["name"] == pname)]
    qual_next = df["qualifiers"].shift(-1)
    type_next = df["type"].shift(-1)
    led_shot = d[
        qual_next.loc[d.index].fillna("").str.contains("KeyPass", na=False)
        | type_next.loc[d.index].fillna("").str.contains("Shot", na=False)
    ]
    led_goal = d[
        qual_next.loc[d.index].fillna("").str.contains("IntentionalGoalAssist", na=False)
        | (type_next.loc[d.index].fillna("") == "Goal")
    ]
    prog = d[(d["prog_carry"] >= config.PROGRESSIVE_DIST) & (d["x"] >= config.PROGRESSIVE_START_X)]
    final_third = d[(d["x"] < config.FINAL_THIRD_X) & (d["endX"] >= config.FINAL_THIRD_X)]
    in_box = (d["endX"] >= config.BOX_X) & (d["endY"] >= config.BOX_Y_MIN) & (d["endY"] <= config.BOX_Y_MAX)
    starts_in_box = (d["x"] >= config.BOX_X) & (d["y"] >= config.BOX_Y_MIN) & (d["y"] <= config.BOX_Y_MAX)
    box_entry = d[in_box & ~starts_in_box]
    dispossessed = len(df[
        (df["type"] == "Carry") & (df["name"] == pname) & (df["type"].shift(-1) == "Dispossessed")
    ])

    take_ons = df[(df["type"] == "TakeOn") & (df["name"] == pname)]
    t_ons = take_ons[take_ons["outcomeType"] == "Successful"]
    success_rate = round(len(t_ons) / len(take_ons) * 100, 2) if len(take_ons) else 0.0

    d = d.copy()
    d["Length"] = np.sqrt((d["x"] - d["endX"]) ** 2 + (d["y"] - d["endY"]) ** 2)
    return {
        "Name": pname,
        "Total_Carries": len(d),
        "Progressive_Carries": len(prog),
        "Carries_Led_to_Shot": len(led_shot),
        "Carries_Led_to_Goal": len(led_goal),
        "Carrier_Dispossessed": dispossessed,
        "Carries_Into_Final_Third": len(final_third),
        "Carries_Into_Penalty_Box": len(box_entry),
        "Avg._Carry_Length": round(d["Length"].median(), 2),
        "Total_Carry_Length": round(d["Length"].sum(), 2),
        "xT_Increased_From_Carries": round(d[d["xT"] > 0]["xT"].sum(), 2),
        "xT_Decreased_From_Carries": round(d[d["xT"] < 0]["xT"].sum(), 2),
        "Total_xT_From_Carries": round(d["xT"].sum(), 2),
        "TakeOn_Attempts": len(take_ons),
        "Successful_TakeOns": len(t_ons),
        "TakeOn_Success_Rate": success_rate,
    }


def shots_from_events(df: pd.DataFrame, pname: str) -> pd.DataFrame:
    """WhoScored shot events for a player as a shots-like frame (no-xG fallback)."""
    d = df[(df["name"] == pname) & (df["type"].isin(config.SHOT_TYPES))].copy()
    if not len(d):
        return pd.DataFrame(columns=["x", "y", "eventType", "expectedGoals",
                                     "expectedGoalsOnTarget", "isBlocked",
                                     "isFromInsideBox", "situation"])
    d["eventType"] = d["type"].map({"Goal": "Goal", "MissedShots": "Miss",
                                    "SavedShot": "AttemptSaved", "ShotOnPost": "Post"})
    d["expectedGoals"] = 0.0
    d["expectedGoalsOnTarget"] = 0.0
    d["isBlocked"] = d["qualifiers"].str.contains("Blocked", na=False)
    d["isFromInsideBox"] = ~d["qualifiers"].str.contains("OutOfBox", na=False)
    d["situation"] = "RegularPlay"
    return d[["x", "y", "eventType", "expectedGoals", "expectedGoalsOnTarget",
              "isBlocked", "isFromInsideBox", "situation"]]


def player_shot_frame(df: pd.DataFrame, pname: str, shots_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """UEFA-scaled shot rows for one player: FotMob shots (with xG) when
    available, else WhoScored events. Columns: x, y, eventType, expectedGoals,
    expectedGoalsOnTarget, isBlocked, isFromInsideBox, situation."""
    fm = fotmob_shots_for(shots_df, pname)
    if len(fm):
        out = fm[["x", "y", "eventType", "expectedGoals", "expectedGoalsOnTarget",
                  "isBlocked", "isFromInsideBox", "situation"]].copy()
        out["x"] = pd.to_numeric(out["x"], errors="coerce") * config.X_SCALE
        out["y"] = pd.to_numeric(out["y"], errors="coerce") * config.Y_SCALE
        out["expectedGoals"] = out["expectedGoals"].fillna(0)
        out["expectedGoalsOnTarget"] = out["expectedGoalsOnTarget"].fillna(0)
        return out.dropna(subset=["x", "y"])
    return shots_from_events(df, pname)


def fotmob_shots_for(shots_df: pd.DataFrame | None, pname: str) -> pd.DataFrame:
    """FotMob shots for a player (matches full name, falls back to short name)."""
    if shots_df is None or not len(shots_df):
        return pd.DataFrame()
    by_name = shots_df[shots_df["playerName"] == pname]
    if len(by_name):
        return by_name.copy()
    short = core_events.short_name(pname)
    return shots_df[shots_df["shortName"].fillna("") == short].copy()


def shooting_stats(df: pd.DataFrame, pname: str, shots_df: pd.DataFrame | None = None) -> dict:
    shots = df[(df["name"] == pname) & (df["type"].isin(config.SHOT_TYPES))].copy()
    big = shots["qualifiers"].str.contains("BigChance", na=False)
    goals = len(shots[shots["type"] == "Goal"])
    posts = len(shots[shots["type"] == "ShotOnPost"])
    on_target = len(shots[shots["type"] == "SavedShot"])
    off_target = len(shots[shots["type"] == "MissedShots"])
    out_box = len(shots[shots["qualifiers"].str.contains("OutOfBox", na=False)])

    shots["Length"] = np.sqrt((shots["x"] - config.PITCH_X_MAX) ** 2
                              + (shots["y"] - config.GOAL_CENTER[1]) ** 2)
    avg_dist = round(shots["Length"].mean(), 2) if len(shots) else 0.0

    xg = xgot = 0.0
    fm = fotmob_shots_for(shots_df, pname)
    if len(fm):
        xg = round(fm["expectedGoals"].fillna(0).sum(), 2)
        xgot = round(fm["expectedGoalsOnTarget"].fillna(0).sum(), 2)

    return {
        "Name": pname,
        "Total_Shots": len(shots),
        "Goals": goals,
        "Shot_On_Post": posts,
        "Shot_On_Target": on_target,
        "Shot_Off_Target": off_target,
        "Big_Chances": int(big.sum()),
        "Big_Chances_Missed": int((big & (shots["type"] != "Goal")).sum()),
        "Shots_From_Outside_The_Box": out_box,
        "Shots_From_Inside_The_Box": len(shots) - out_box,
        "Avg._Shot_Distance": avg_dist,
        "xG": xg,
        "xGOT": xgot,
    }


def pass_receiving_stats(df: pd.DataFrame, pname: str) -> dict:
    d = df[
        (df["type"] == "Pass") & (df["outcomeType"] == "Successful")
        & (df["name"].shift(-1) == pname)
    ]
    key_recv = d[d["qualifiers"].str.contains("KeyPass", na=False)]
    assist_recv = d[d["qualifiers"].str.contains("IntentionalGoalAssist", na=False)]
    final_third = d[d["endX"] >= config.FINAL_THIRD_X]
    pen_box = d[
        (d["endX"] >= config.BOX_X - 0.5) & (d["endY"] >= config.BOX_Y_MIN)
        & (d["endY"] <= config.BOX_Y_MAX)
    ]
    prog_recv = d[
        (d["x"] >= config.PROGRESSIVE_START_X) & (d["prog_pass"] >= config.PROGRESSIVE_DIST)
        & (~d["qualifiers"].str.contains("CornerTaken|Freekick", na=False))
    ]
    crosses_recv = d[d["qualifiers"].str.contains("Cross", na=False)]
    longballs_recv = d[d["qualifiers"].str.contains("Longball", na=False)]
    cutbacks = d[
        (d["x"] >= 88.54) & ((d["y"] >= 40.8) | (d["y"] <= 27.2))
        & (d["endY"] >= 27.2) & (d["endY"] <= 40.8) & (d["endX"] >= 81.67)
    ]
    xt_recv = d[d["xT"] >= 0]["xT"].sum()

    next_act = df[
        (df["name"] == pname) & (df["type"].shift(1) == "Pass")
        & (df["outcomeType"].shift(1) == "Successful")
    ]
    retained = next_act[next_act["outcomeType"] == "Successful"]
    ball_retention = round(len(retained) / len(next_act) * 100, 2) if len(next_act) else 0.0

    if len(d):
        passer_counts = _short_name_series(d["name"]).value_counts()
        top_passer = passer_counts.index[0]
        top_count = int(passer_counts.iloc[0])
        avg_goal_line_dist = round(105 - d["endX"].median(), 2)
    else:
        top_passer, top_count, avg_goal_line_dist = "None", 0, 0.0

    return {
        "Name": pname,
        "Total_Passes_Received": len(d),
        "Key_Passes_Received": len(key_recv),
        "Assists_Received": len(assist_recv),
        "Progressive_Passes_Received": len(prog_recv),
        "Passes_Received_In_Final_Third": len(final_third),
        "Passes_Received_In_Opponent_Penalty_Box": len(pen_box),
        "Crosses_Received": len(crosses_recv),
        "Longballs_Received": len(longballs_recv),
        "Cutbacks_Received": len(cutbacks),
        "Ball_Retention": ball_retention,
        "xT_Received": round(xt_recv, 2),
        "Avg._Distance_Of_Pass_Receiving_From_Oppo._Goal_Line": avg_goal_line_dist,
        "Most_Passes_Received_From_(Count)": f"{top_passer}({top_count})",
    }


def defensive_stats(df: pd.DataFrame, pname: str) -> dict:
    d = df[df["name"] == pname]
    ball_wins = d[(d["type"] == "Interception") | (d["type"] == "BallRecovery")]

    def wins_in_third(zone: str) -> int:
        if zone == "F":
            return len(ball_wins[ball_wins["x"] >= config.FINAL_THIRD_X])
        if zone == "M":
            return len(ball_wins[
                (ball_wins["x"] > config.PROGRESSIVE_START_X)
                & (ball_wins["x"] < config.FINAL_THIRD_X)
            ])
        return len(ball_wins[ball_wins["x"] <= config.PROGRESSIVE_START_X])

    tackles = d[d["type"] == "Tackle"]
    tackles_lost = tackles[tackles["outcomeType"] == "Unsuccessful"]
    interceptions = d[d["type"] == "Interception"]
    recoveries = d[d["type"] == "BallRecovery"]
    clearances = d[d["type"] == "Clearance"]
    fouls = d[d["type"] == "Foul"]
    aerials = d[(d["type"] == "Aerial") & d["qualifiers"].str.contains("Defensive", na=False)]
    aerials_lost = aerials[aerials["outcomeType"] == "Unsuccessful"]
    pass_blocks = d[d["type"] == "BlockedPass"]
    shot_blocks = d[
        d["type"].isin(config.SHOT_TYPES) & d["qualifiers"].str.contains("Blocked", na=False)
    ]
    dribbled_past = d[d["type"] == "Challenge"]
    dribblers_tackled = df[
        (df["name"] == pname) & (df["type"] == "Tackle")
        & (df["type"].shift(1) == "TakeOn") & (df["outcomeType"].shift(1) == "Unsuccessful")
    ]
    err_to_shot = d[d["qualifiers"].str.contains("LeadingToAttempt", na=False)]
    err_to_goal = d[d["qualifiers"].str.contains("LeadingToGoal", na=False)]
    dangerous_fouls = d[
        (d["type"] == "Foul") & (d["x"] > 16.5) & (d["x"] < config.PROGRESSIVE_START_X)
        & (d["y"] > config.BOX_Y_MIN) & (d["y"] < config.BOX_Y_MAX)
    ]

    # Next event after a recovery/interception is a successful action (retained)
    nxt = df[(df["type"] == "BallRecovery") | (df["type"] == "Interception")]
    nxt = nxt[(nxt["name"] == pname) & (nxt["outcomeType"].shift(-1) == "Successful")]
    post_rec_retention = round(len(nxt) / (len(recoveries) + len(interceptions)) * 100, 2) \
        if (len(recoveries) + len(interceptions)) else 0.0

    return {
        "Name": pname,
        "Total_Tackles": len(tackles),
        "Tackles_Won": len(tackles) - len(tackles_lost),
        "Dribblers_Tackled": len(dribblers_tackled),
        "Dribble_Past": len(dribbled_past),
        "Interception": len(interceptions),
        "Ball_Recoveries": len(recoveries),
        "Post_Recovery_Ball_Retention": post_rec_retention,
        "Pass_Blocked": len(pass_blocks),
        "Ball_Clearances": len(clearances),
        "Shots_Blocked": len(shot_blocks),
        "Aerial_Duels": len(aerials),
        "Aerial_Duels_Won": len(aerials) - len(aerials_lost),
        "Fouls_Committed": len(fouls),
        "Fouls_Infront_Of_Own_Penalty_Box": len(dangerous_fouls),
        "Error_Led_to_Shot": len(err_to_shot),
        "Error_Led_to_Goal": len(err_to_goal),
        "Possession_Win_Final_third": wins_in_third("F"),
        "Possession_Win_Mid_third": wins_in_third("M"),
        "Possession_Win_Defensive_third": wins_in_third("D"),
    }


def touches_stats(df: pd.DataFrame, pname: str) -> dict:
    d = df[df["name"] == pname]
    touches = d[
        (d["isTouch"] == True) & (~d["type"].str.contains("SubstitutionOff|SubstitutionOn|Card|Carry", na=False))  # noqa: E712
    ]
    final_third = touches[touches["x"] >= config.FINAL_THIRD_X]
    pen_box = touches[
        (touches["x"] >= config.BOX_X) & (touches["y"] >= config.BOX_Y_MIN)
        & (touches["y"] <= config.BOX_Y_MAX)
    ]

    area_covered = 0.0
    pts = touches[["x", "y"]].dropna().values
    if len(pts) >= 3:
        try:
            hull = ConvexHull(pts)
            area_covered = round(hull.volume, 2)
        except QhullError:
            area_covered = 0.0

    # Distance covered per period (1..4; numeric periods in the master frame)
    pos = d[~d["type"].str.contains("CornerTaken|FreekickTaken|Card|CornerAwarded|SubstitutionOff|SubstitutionOn", na=False)]
    pos = pos[["x", "y", "period"]].copy()
    total_km = 0.0
    for period in (1, 2, 3, 4):
        half = pos[pos["period"] == period]
        if len(half) > 1:
            dist = np.sqrt((half["x"] - half["x"].shift(-1)) ** 2
                           + (half["y"] - half["y"].shift(-1)) ** 2).sum()
            total_km += dist / 1000

    return {
        "Name": pname,
        "Total_Touches": len(touches),
        "Touches_In_Final_Third": len(final_third),
        "Touches_In_Opponent_Penalty_Box": len(pen_box),
        "Total_Distance_Covered(Km)": round(total_km, 2),
        "Total_Area_Covered": area_covered,
    }


# --------------------------------------------------------------------------- #
# Playing time + wide table
# --------------------------------------------------------------------------- #

def playing_time(df: pd.DataFrame, pname: str) -> int:
    """Minutes played (max match minute for full starters, else sub windows)."""
    d = df[df["name"] == pname]
    if not len(d):
        return 0
    max_min = int(df["minute"].max())
    sub_off = d[d["type"] == "SubstitutionOff"]
    sub_on = d[d["type"] == "SubstitutionOn"]
    starter = bool(d["isFirstEleven"].dropna().any()) if "isFirstEleven" in d else False

    if starter and not len(sub_off):
        return max_min
    if starter and len(sub_off):
        return int(sub_off["minute"].iloc[0])
    if not starter and len(sub_on):
        return max(0, max_min - int(sub_on["minute"].iloc[0]))
    return 0


def player_stats_table(df: pd.DataFrame, shots_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Merged wide table: one row per player, all six facets + team."""
    facets = [
        lambda n: passing_stats(df, n),
        lambda n: carrying_stats(df, n),
        lambda n: shooting_stats(df, n, shots_df),
        lambda n: pass_receiving_stats(df, n),
        lambda n: defensive_stats(df, n),
        lambda n: touches_stats(df, n),
    ]
    team_of = df.dropna(subset=["name"]).drop_duplicates("name").set_index("name")["teamName"]

    rows = []
    for name in _player_names(df):
        row: dict = {}
        for facet in facets:
            row.update(facet(name))
        row["Team"] = team_of.get(name, "")
        rows.append(row)

    table = pd.DataFrame(rows)
    if len(table):
        table = table.sort_values("Total_Passes", ascending=False).reset_index(drop=True)
    return table


def slugify(name: str) -> str:
    """Safe file stem for a player name."""
    return re.sub(r"[^\w\-]+", "_", name)
