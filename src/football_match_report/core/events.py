"""Event pipeline: raw WhoScored events -> enriched master DataFrame.

Ports the data-prep from the Post-Match-Report-2.0 blueprint:

1. Flatten raw events (display names, snake_case, cumulative minutes).
2. Synthesize ball carries between same-team touches.
3. Compute possession chains (possession_id) for high-turnover analysis.
4. Assign xT values from the 12x8 grid.
5. Progressive pass/carry distances, pass angles.
6. Scale WhoScored 0-100 coordinates to a UEFA 105x68 pitch.
7. Merge player info (name, shirtNo, position, isFirstEleven).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .. import config


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_matchdict(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_players_df(matchdict: dict) -> pd.DataFrame:
    """Concatenated home+away player frames with teamId."""
    frames = []
    for side in ("home", "away"):
        team = matchdict.get(side, {})
        players = pd.DataFrame(team.get("players", []))
        if len(players):
            players["teamId"] = team.get("teamId")
        frames.append(players)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# --------------------------------------------------------------------------- #
# Flattening
# --------------------------------------------------------------------------- #
def flatten_events(matchdict: dict) -> pd.DataFrame:
    """Raw events -> DataFrame with display-name columns and cumulative minutes."""
    events = matchdict.get("events", [])
    df = pd.DataFrame(events)

    def display(x):
        return x.get("displayName") if isinstance(x, dict) else None

    df["type"] = df["type"].apply(display)
    df["outcomeType"] = df["outcomeType"].apply(display)
    df["period"] = df["period"].apply(display)
    df["period"] = df["period"].replace(
        {"FirstHalf": 1, "SecondHalf": 2, "FirstPeriodOfExtraTime": 3,
         "SecondPeriodOfExtraTime": 4, "PenaltyShootout": 5,
         "PostGame": 14, "PreMatch": 16}
    )

    df = df.reset_index(drop=True)
    df["index"] = np.arange(1, len(df) + 1)
    df["qualifiers"] = df["qualifiers"].apply(json.dumps) if "qualifiers" in df.columns else ""
    df["cumulative_mins"] = _cumulative_match_mins(df)
    return df


def _cumulative_match_mins(events_df: pd.DataFrame) -> pd.Series:
    """Cumulative minutes across periods (blueprint logic)."""
    match_events = events_df.copy()
    match_events["cumulative_mins"] = match_events["minute"] + (1 / 60) * match_events["second"]
    for period in np.arange(1, match_events["period"].max() + 1, 1):
        if period > 1:
            t_delta = (
                match_events[match_events["period"] == period - 1]["cumulative_mins"].max()
                - match_events[match_events["period"] == period]["cumulative_mins"].min()
            )
        else:
            t_delta = 0
        match_events.loc[match_events["period"] == period, "cumulative_mins"] += t_delta
    return match_events["cumulative_mins"]


# --------------------------------------------------------------------------- #
# Ball carries
# --------------------------------------------------------------------------- #
def insert_ball_carries(
    events_df: pd.DataFrame,
    min_carry_length: float = 3.0,
    max_carry_length: float = 60.0,
    min_carry_duration: float = 1.0,
    max_carry_duration: float = 10.0,
) -> pd.DataFrame:
    """Synthesize Carry events between same-team consecutive touches."""
    match_events = events_df.reset_index(drop=True)
    match_carries = pd.DataFrame()

    for idx, match_event in match_events.iterrows():
        if idx >= len(match_events) - 1:
            continue
        prev_evt_team = match_event["teamId"]
        next_evt_idx = idx + 1
        init_next_evt = match_events.loc[next_evt_idx]
        take_ons = 0

        # Walk forward past take-ons / challenges / fouls
        while True:
            next_evt = match_events.loc[next_evt_idx]
            if next_evt["type"] == "TakeOn" and next_evt["outcomeType"] == "Successful":
                take_ons += 1
                next_evt_idx += 1
            elif (
                (next_evt["type"] == "TakeOn" and next_evt["outcomeType"] == "Unsuccessful")
                or (next_evt["teamId"] != prev_evt_team and next_evt["type"] == "Challenge"
                    and next_evt["outcomeType"] == "Unsuccessful")
                or (next_evt["type"] == "Foul")
            ):
                next_evt_idx += 1
            else:
                break

        same_team = prev_evt_team == next_evt["teamId"]
        not_ball_touch = match_event["type"] != "BallTouch"
        dx = 105 * (match_event["endX"] - next_evt["x"]) / 100
        dy = 68 * (match_event["endY"] - next_evt["y"]) / 100
        far_enough = dx**2 + dy**2 >= min_carry_length**2
        not_too_far = dx**2 + dy**2 <= max_carry_length**2
        dt = 60 * (next_evt["cumulative_mins"] - match_event["cumulative_mins"])
        min_time = dt >= min_carry_duration
        same_phase = dt < max_carry_duration
        same_period = match_event["period"] == next_evt["period"]

        if same_team and not_ball_touch and far_enough and not_too_far and min_time and same_phase and same_period:
            carry = pd.DataFrame([{}])
            carry.loc[0, "eventId"] = match_event["eventId"] + 0.5
            carry.loc[0, "minute"] = np.floor(
                ((init_next_evt["minute"] * 60 + init_next_evt["second"])
                 + (match_event["minute"] * 60 + match_event["second"])) / (2 * 60)
            )
            carry.loc[0, "second"] = (
                ((init_next_evt["minute"] * 60 + init_next_evt["second"])
                 + (match_event["minute"] * 60 + match_event["second"])) / 2
            ) - (carry.loc[0, "minute"] * 60)
            carry.loc[0, "teamId"] = next_evt["teamId"]
            carry.loc[0, "x"] = match_event["endX"]
            carry.loc[0, "y"] = match_event["endY"]
            carry.loc[0, "expandedMinute"] = np.floor(
                ((init_next_evt["expandedMinute"] * 60 + init_next_evt["second"])
                 + (match_event["expandedMinute"] * 60 + match_event["second"])) / (2 * 60)
            )
            carry.loc[0, "period"] = next_evt["period"]
            carry.loc[0, "type"] = "Carry"
            carry.loc[0, "outcomeType"] = "Successful"
            carry.loc[0, "qualifiers"] = json.dumps(
                {"type": {"value": 999, "displayName": "takeOns"}, "value": str(take_ons)}
            )
            carry.loc[0, "satisfiedEventsTypes"] = json.dumps([])
            carry.loc[0, "isTouch"] = True
            carry.loc[0, "playerId"] = next_evt["playerId"]
            carry.loc[0, "endX"] = next_evt["x"]
            carry.loc[0, "endY"] = next_evt["y"]
            carry.loc[0, "blockedX"] = np.nan
            carry.loc[0, "blockedY"] = np.nan
            carry.loc[0, "goalMouthZ"] = np.nan
            carry.loc[0, "goalMouthY"] = np.nan
            carry.loc[0, "isShot"] = np.nan
            carry.loc[0, "relatedEventId"] = next_evt["eventId"]
            carry.loc[0, "relatedPlayerId"] = np.nan
            carry.loc[0, "isGoal"] = np.nan
            carry.loc[0, "cardType"] = np.nan
            carry.loc[0, "isOwnGoal"] = np.nan
            carry.loc[0, "cumulative_mins"] = (
                match_event["cumulative_mins"] + init_next_evt["cumulative_mins"]
            ) / 2
            match_carries = pd.concat([match_carries, carry], ignore_index=True, sort=False)

    combined = pd.concat([match_carries, match_events], ignore_index=True, sort=False)
    combined = combined.sort_values(["period", "cumulative_mins"]).reset_index(drop=True)
    return combined


# --------------------------------------------------------------------------- #
# Possession chains (for high turnovers)
# --------------------------------------------------------------------------- #
def add_possession_chains(events_df: pd.DataFrame, chain_check: int = 7, suc_evts_in_chain: int = 2) -> pd.DataFrame:
    """Assign possession_id / possession_team per event (blueprint logic)."""
    df = events_df.copy().reset_index(drop=True)
    if "teamBinary" not in df.columns:
        teams = df["teamId"].unique()
        df["teamBinary"] = df["teamId"].map({t: i for i, t in enumerate(teams)})
    df["goalBinary"] = (df["type"] == "Goal").astype(int)

    match_pos_events_df = df[["teamBinary", "goalBinary", "period", "teamName"]].copy()
    pos_chain_df = pd.DataFrame(index=df.index)

    for n in np.arange(1, chain_check):
        pos_chain_df[f"evt_{n}_same_team"] = abs(match_pos_events_df["teamBinary"].diff(periods=-n))
        pos_chain_df[f"evt_{n}_same_team"] = pos_chain_df[f"evt_{n}_same_team"].apply(lambda x: 1 if x > 1 else x)
    pos_chain_df["enough_evt_same_team"] = (
        pos_chain_df.sum(axis=1).apply(lambda x: 1 if x < chain_check - suc_evts_in_chain else 0)
    )
    pos_chain_df["enough_evt_same_team"] = pos_chain_df["enough_evt_same_team"].diff(periods=1)
    pos_chain_df.loc[pos_chain_df["enough_evt_same_team"] < 0, "enough_evt_same_team"] = 0

    match_pos_events_df["period"] = pd.to_numeric(match_pos_events_df["period"], errors="coerce")
    pos_chain_df["upcoming_ko"] = 0
    for ko in match_pos_events_df[
        (match_pos_events_df["goalBinary"] == 1) | (match_pos_events_df["period"].diff(periods=1) != 0)
    ].index.values:
        ko_pos = match_pos_events_df.index.to_list().index(ko)
        start = max(ko_pos - suc_evts_in_chain, 0)
        pos_chain_df.iloc[start:ko_pos, pos_chain_df.columns.get_loc("upcoming_ko")] = 1

    pos_chain_df["valid_pos_start"] = pos_chain_df.fillna(0)["enough_evt_same_team"] - pos_chain_df.fillna(0)["upcoming_ko"]
    pos_chain_df["kick_off_period_change"] = match_pos_events_df["period"].diff(periods=1)
    pos_chain_df["kick_off_goal"] = (
        (match_pos_events_df["type"] == "Goal").astype(int).diff(periods=1).apply(lambda x: 1 if x < 0 else 0)
    ) if "type" in match_pos_events_df else 0
    pos_chain_df.loc[pos_chain_df["kick_off_period_change"] == 1, "valid_pos_start"] = 1
    pos_chain_df.loc[pos_chain_df["kick_off_goal"] == 1, "valid_pos_start"] = 1

    pos_chain_df["teamName"] = match_pos_events_df["teamName"]
    pos_chain_df.loc[pos_chain_df.head(1).index, "valid_pos_start"] = 1
    pos_chain_df.loc[pos_chain_df.head(1).index, "possession_id"] = 1
    pos_chain_df.loc[pos_chain_df.head(1).index, "possession_team"] = pos_chain_df.loc[
        pos_chain_df.head(1).index, "teamName"
    ]

    valid_pos_start_id = pos_chain_df[pos_chain_df["valid_pos_start"] > 0].index
    possession_id = 2
    for i in range(1, len(valid_pos_start_id)):
        row_id = valid_pos_start_id[i]
        pos_chain_df.loc[row_id, "possession_id"] = possession_id
        pos_chain_df.loc[row_id, "possession_team"] = pos_chain_df.loc[row_id, "teamName"]
        possession_id += 1

    pos_chain_df[["possession_id", "possession_team"]] = pos_chain_df[["possession_id", "possession_team"]].ffill()
    pos_chain_df[["possession_id", "possession_team"]] = pos_chain_df[["possession_id", "possession_team"]].bfill()

    df["possession_id"] = pos_chain_df["possession_id"].values
    df["possession_team"] = pos_chain_df["possession_team"].values
    return df


# --------------------------------------------------------------------------- #
# xT values
# --------------------------------------------------------------------------- #
def assign_xt(events_df: pd.DataFrame, xt_grid: np.ndarray) -> pd.DataFrame:
    """Assign start/end zone values and xT to Pass/Carry events (0-100 coords)."""
    df = events_df.copy()
    dfxT = df[(~df["qualifiers"].str.contains("Corner", na=False))]
    dfxT = dfxT[(dfxT["type"].isin(["Pass", "Carry"])) & (dfxT["outcomeType"] == "Successful")].copy()

    xT_rows, xT_cols = xt_grid.shape
    dfxT["x1_bin_xT"] = pd.cut(dfxT["x"], bins=xT_cols, labels=False)
    dfxT["y1_bin_xT"] = pd.cut(dfxT["y"], bins=xT_rows, labels=False)
    dfxT["x2_bin_xT"] = pd.cut(dfxT["endX"], bins=xT_cols, labels=False)
    dfxT["y2_bin_xT"] = pd.cut(dfxT["endY"], bins=xT_rows, labels=False)

    dfxT["start_zone_value_xT"] = dfxT[["x1_bin_xT", "y1_bin_xT"]].apply(
        lambda r: xt_grid[int(r.iloc[1])][int(r.iloc[0])]
        if not pd.isna(r.iloc[1]) and not pd.isna(r.iloc[0]) else np.nan, axis=1
    )
    dfxT["end_zone_value_xT"] = dfxT[["x2_bin_xT", "y2_bin_xT"]].apply(
        lambda r: xt_grid[int(r.iloc[1])][int(r.iloc[0])]
        if not pd.isna(r.iloc[1]) and not pd.isna(r.iloc[0]) else np.nan, axis=1
    )
    dfxT["xT"] = dfxT["end_zone_value_xT"] - dfxT["start_zone_value_xT"]
    dfxT = dfxT[["index", "xT", "start_zone_value_xT", "end_zone_value_xT"]]

    return df.merge(dfxT, on="index", how="left")


# --------------------------------------------------------------------------- #
# Master pipeline
# --------------------------------------------------------------------------- #
def build_master_df(matchdict: dict, xt_grid: np.ndarray) -> pd.DataFrame:
    """Full enriched event frame ready for every chart."""
    players_df = build_players_df(matchdict)
    teams_dict = {
        matchdict["home"]["teamId"]: matchdict["home"]["name"],
        matchdict["away"]["teamId"]: matchdict["away"]["name"],
    }

    df = flatten_events(matchdict)
    df = insert_ball_carries(df)
    df = df.reset_index(drop=True)
    df["index"] = np.arange(1, len(df) + 1)

    df = assign_xt(df, xt_grid)

    df["teamName"] = df["teamId"].map(teams_dict)
    team_names = list(teams_dict.values())
    opposition_dict = {team_names[i]: team_names[1 - i] for i in range(len(team_names))}
    df["oppositionTeamName"] = df["teamName"].map(opposition_dict)

    # Scale 0-100 -> UEFA 105x68
    df["x"] = df["x"] * config.X_SCALE
    df["y"] = df["y"] * config.Y_SCALE
    df["endX"] = df["endX"] * config.X_SCALE
    df["endY"] = df["endY"] * config.Y_SCALE
    df["goalMouthY"] = df["goalMouthY"] * config.Y_SCALE

    # Player info
    dfp = players_df.copy()
    for col in ["height", "weight", "age", "isManOfTheMatch", "field", "stats",
                "subbedInPlayerId", "subbedOutPeriod", "subbedOutExpandedMinute",
                "subbedInPeriod", "subbedInExpandedMinute", "subbedOutPlayerId", "teamId"]:
        if col in dfp.columns:
            dfp = dfp.drop(columns=[col])
    df = df.merge(dfp, on="playerId", how="left")

    df["qualifiers"] = df["qualifiers"].astype(str)

    # Progressive pass / carry distances (toward home goal at x=105)
    df["prog_pass"] = np.where(
        df["type"] == "Pass",
        np.sqrt((105 - df["x"]) ** 2 + (34 - df["y"]) ** 2)
        - np.sqrt((105 - df["endX"]) ** 2 + (34 - df["endY"]) ** 2),
        0,
    )
    df["prog_carry"] = np.where(
        df["type"] == "Carry",
        np.sqrt((105 - df["x"]) ** 2 + (34 - df["y"]) ** 2)
        - np.sqrt((105 - df["endX"]) ** 2 + (34 - df["endY"]) ** 2),
        0,
    )
    df["pass_or_carry_angle"] = np.degrees(np.arctan2(df["endY"] - df["y"], df["endX"] - df["x"]))
    df["name"] = df["name"].astype(str)
    df = add_possession_chains(df)

    return df


def load_xt_grid(path: str | Path) -> np.ndarray:
    grid_path = Path(path)
    if not grid_path.exists():
        grid_path = Path(__file__).resolve().parent.parent / "data" / "xt_grid.csv"
    return np.array(pd.read_csv(grid_path, header=None))


def short_name(full_name: str) -> str:
    """'A. Salah' style short name."""
    if pd.isna(full_name):
        return full_name
    parts = str(full_name).split()
    if len(parts) == 1:
        return full_name
    if len(parts) == 2:
        return f"{parts[0][0]}. {parts[1]}"
    return f"{parts[0][0]}. {' '.join(parts[1:])}"
