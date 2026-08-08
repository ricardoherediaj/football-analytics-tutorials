"""Shared fixtures: a tiny synthetic match bundle for offline tests."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(scope="session")
def synthetic_matchdict() -> dict:
    """A small but realistic WhoScored matchCentreData dict (home 2-1 away)."""
    events = []
    # Two kickoffs, then a handful of passes/shots per team
    for team_id, side in ((1, "home"), (2, "away")):
        events.append({
            "id": len(events) + 1, "eventId": len(events) + 1, "minute": 0, "second": 0,
            "teamId": team_id, "playerId": None, "type": {"displayName": "Start"},
            "outcomeType": {"displayName": "Successful"}, "period": {"displayName": "FirstHalf"},
            "x": 0.0, "y": 0.0, "endX": 0.0, "endY": 0.0, "isTouch": False,
            "qualifiers": [], "expandedMinute": 0,
        })

    pass_specs = [
        # (team, minute, x, y, endX, endY, outcome, qualifiers)
        (1, 1, 50, 50, 60, 50, "Successful", []),
        (1, 2, 60, 50, 75, 40, "Successful", []),
        (1, 3, 75, 40, 88, 34, "Successful", [{"type": {"displayName": "KeyPass"}}]),
        (2, 4, 45, 45, 40, 45, "Successful", []),
        (2, 5, 40, 45, 30, 40, "Successful", []),
        (1, 6, 88, 34, 97, 34, "Successful", []),
        (1, 7, 97, 34, 102, 34, "Successful", [{"type": {"displayName": "IntentionalGoalAssist"}}]),
        (2, 8, 30, 40, 25, 35, "Unsuccessful", []),
        (1, 9, 50, 30, 60, 35, "Successful", []),
        (2, 10, 25, 35, 15, 30, "Successful", []),
    ]
    for (team, minute, x, y, ex, ey, outcome, quals) in pass_specs:
        events.append({
            "id": len(events) + 1, "eventId": len(events) + 1, "minute": minute, "second": 0,
            "teamId": team, "playerId": 1000 + team * 100,
            "type": {"displayName": "Pass"}, "outcomeType": {"displayName": outcome},
            "period": {"displayName": "FirstHalf"},
            "x": float(x), "y": float(y), "endX": float(ex), "endY": float(ey),
            "isTouch": True, "qualifiers": quals, "expandedMinute": minute,
        })

    # Shots: home goal at 12', home miss at 14', away goal at 20'
    shot_specs = [
        (1, 12, 98, 34, "Goal", [{"type": {"displayName": "BigChance"}}]),
        (1, 14, 95, 30, "MissedShots", []),
        (2, 20, 15, 34, "Goal", []),
        (2, 22, 12, 20, "SavedShot", []),
        (2, 25, 10, 30, "MissedShots", [{"type": {"displayName": "BigChance"}}]),
    ]
    for (team, minute, x, y, etype, quals) in shot_specs:
        events.append({
            "id": len(events) + 1, "eventId": len(events) + 1, "minute": minute, "second": 0,
            "teamId": team, "playerId": 1000 + team * 100,
            "type": {"displayName": etype}, "outcomeType": {"displayName": "Successful"},
            "period": {"displayName": "FirstHalf"},
            "x": float(x), "y": float(y), "endX": float(x), "endY": float(y),
            "isTouch": True, "qualifiers": quals, "expandedMinute": minute,
            "goalMouthY": 40.0, "goalMouthZ": 20.0,
        })

    # Defensive actions
    for (team, minute, x, y, etype) in [
        (1, 15, 40, 30, "Tackle"), (1, 16, 35, 40, "Interception"),
        (2, 17, 60, 30, "Clearance"), (1, 18, 50, 20, "BallRecovery"),
    ]:
        events.append({
            "id": len(events) + 1, "eventId": len(events) + 1, "minute": minute, "second": 0,
            "teamId": team, "playerId": 1000 + team * 100,
            "type": {"displayName": etype}, "outcomeType": {"displayName": "Successful"},
            "period": {"displayName": "FirstHalf"},
            "x": float(x), "y": float(y), "endX": float(x), "endY": float(y),
            "isTouch": True, "qualifiers": [], "expandedMinute": minute,
        })

    def players(team_id, n):
        return [
            {"playerId": 1000 + team_id * 100 + i, "name": f"P{team_id}A{i}", "shirtNo": 1 + i,
             "position": "GK" if i == 0 else ("DC" if i == 1 else "MC"), "isFirstEleven": True}
            for i in range(n)
        ]

    return {
        "home": {"name": "Hometeam", "teamId": 1, "players": players(1, 4)},
        "away": {"name": "Awayteam", "teamId": 2, "players": players(2, 4)},
        "events": events,
        "playerIdNameDictionary": {},
        "score": "2 : 1",
        "ftScore": "2 : 1",
        "htScore": "1 : 0",
        "startDate": "2025-01-01T00:00:00",
        "venueName": "Test Stadium",
        "attendance": 1000,
        "referee": "Referee",
    }


@pytest.fixture(scope="session")
def synthetic_bundle(tmp_path_factory, synthetic_matchdict) -> Path:
    """Write a full bundle dir (matchdict.json + xt grid) for render tests."""
    out = tmp_path_factory.mktemp("bundle")
    (out / "matchdict.json").write_text(json.dumps(synthetic_matchdict))
    # minimal meta
    meta = {
        "teams": {
            "home": {"name": "Hometeam", "who_scored_id": 1, "fotmob_id": 100},
            "away": {"name": "Awayteam", "who_scored_id": 2, "fotmob_id": 200},
        },
        "score": {"home": 2, "away": 1},
        "ft_score": {"home": 2, "away": 1},
        "competition": "Test League",
        "colors": {"100": "#00a0de", "200": "#ff4b44"},
    }
    (out / "meta.json").write_text(json.dumps(meta))
    grid = np.array([[0.006, 0.007, 0.008, 0.009, 0.011, 0.012, 0.014, 0.017, 0.021, 0.027, 0.034, 0.037]] * 8)
    pd.DataFrame(grid).to_csv(out / "xt_grid.csv", index=False, header=False)
    return out
