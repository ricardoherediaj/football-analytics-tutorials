"""Global constants: colors, pitch config, metric thresholds."""

# ---- Palette (black theme, blueprint-style) ----
BG_COLOR = "#000000"
LINE_COLOR = "#FFFFFF"
GREEN = "#69f900"
RED = "#ff4b44"
BLUE = "#00a0de"
VIOLET = "#a369ff"
ORANGE = "#FF8C00"
GRAY = "#808080"
YELLOW = "#FFFF00"

# Fallback team colors (real colors come from FotMob teamColors payload)
FALLBACK_HOME = "#00a0de"
FALLBACK_AWAY = "#ff4b44"

# ---- Pitch ----
# WhoScored events arrive in a 0-100 space; the blueprint renders on a
# UEFA 105x68 pitch, so x*1.05, y*0.68.
PITCH_TYPE = "uefa"
X_SCALE = 1.05
Y_SCALE = 0.68
PITCH_X_MAX = 105.0
PITCH_Y_MAX = 68.0
GOAL_CENTER = (105.0, 34.0)  # used for progressive distance (home goal)

# ---- Event types ----
DEFENSIVE_TYPES = [
    "Aerial", "BallRecovery", "BlockedPass", "Challenge", "Clearance",
    "Error", "Foul", "Interception", "Tackle",
]
SHOT_TYPES = ["Goal", "MissedShots", "SavedShot", "ShotOnPost"]

# ---- Metric thresholds (blueprint values, in UEFA meters) ----
PROGRESSIVE_DIST = 9.11      # min distance gained toward goal (yards)
PROGRESSIVE_START_X = 35.0   # passes must start outside the defensive third
FINAL_THIRD_X = 70.0
BOX_X = 88.5                 # penalty box start
BOX_Y_MIN, BOX_Y_MAX = 13.6, 54.6
HIGH_TURNOVER_DIST = 40.0    # metres from opponent goal

# ---- Zones for pass/entry splits (UEFA y-axis thirds) ----
ZONE_TOP, ZONE_BOT = 45.33, 22.67

# ---- Zone 14 & half-spaces ----
Z14_X_MIN, Z14_X_MAX = 70.0, 88.54
Z14_Y_MIN, Z14_Y_MAX = 22.66, 45.32
HS_Y1_MIN, HS_Y1_MAX = 11.33, 22.66
HS_Y2_MIN, HS_Y2_MAX = 45.32, 56.95
