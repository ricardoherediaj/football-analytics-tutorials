# Metric Definitions & Interpretation

Reference for every metric the report computes. All values are derived
on the fly from the scraped WhoScored event stream and FotMob shot map —
nothing is hardcoded per match.

## Pitch & coordinate conventions

- **WhoScored events** arrive in a 0-100 space (both axes). The pipeline
  scales them to **StatsBomb 120 × 80** (x × 1.2, y × 0.8) so all pitch
  plots use the same convention. Teams are assumed to attack left → right
  in the source data; the shot map flips coordinates per team so shots sit
  at the correct end.
- **FotMob shots** arrive as percentages of the pitch (0-100); they are
  scaled to 120 × 80 with `x/100*120`, `y/100*80`.

## Event-stream metrics (WhoScored)

| Metric | Definition |
|--------|-----------|
| **Possession** | Share of total passes attempted by each team (WhoScored event count), not Opta-style time-based possession. |
| **Passes (Acc.)** | Successful pass events per team. |
| **Pass Accuracy %** | Successful passes ÷ total passes × 100. |
| **LongBalls (Acc.)** | Successful passes carrying the `Longball` qualifier. |
| **Tackles (Wins)** | Tackle events with a `Successful` outcome. |
| **Interceptions / Clearances / Aerials (Wins)** | Event counts; aerials counted only when successful. |
| **PPDA** | Opponent passes allowed in the opponent's 60% (x < 72) ÷ own defensive actions (Tackle/Interception/Foul/Challenge) in the opponent's 40% (x > 48). Lower = more aggressive pressing. ~10-12 is elite pressing; >15 is passive. |
| **Field Tilt** | Share of each team's touches in the final third (x > 96). ~60/40 means the leading team dominated territory. |
| **High Turnovers** | Ball recoveries + interceptions in the attacking third (x > 80). A proxy for winning the ball high. |
| **Progressive Passes** | Successful passes that advance play ≥ 10m toward the opponent goal (end_x − x ≥ 10), starting from the middle third (x ≥ 42), set pieces excluded. |

## Shot / xG metrics (FotMob)

| Metric | Definition |
|--------|-----------|
| **xG** | Sum of `expectedGoals` over the team's shots (model: FotMob's). |
| **Shots / On Target** | Shot map rows; `isOnTarget` flags on-target attempts. |
| **Big Chances** | Shots with a `BigChance` situation qualifier. |
| **Goals** | Shot events typed `Goal`, own goals excluded. |

## Timeline panels

- **xG timeline**: cumulative expected goals per team across match minutes
  (step-plot). Steep segments = a cluster of high-quality chances.
- **Match momentum**: FotMob's native momentum series (positive = home
  advantage, negative = away). Used verbatim when available — no custom
  re-implementation, which keeps the code small and the number trustworthy.

## Passing network construction

1. Successful passes only; receiver = next event's `player_id` (WhoScored
   links events sequentially).
2. Player nodes: median x/y of each player's passes, players with ≥ 5 passes.
3. Edges: bidirectional pass pairs with ≥ 3 completed connections; edge
   alpha and width scale with connection count.
4. Top 6 players by pass volume get name labels.

## Reading the dashboard

- **Passing networks**: node spread shows the team's shape; a narrow
  vertical cluster in the middle third = low block; arrows/edges toward the
  opponent goal = penetration.
- **Shot map**: big circles = high-xG chances. A team with high xG but few
  goals underperformed (or met a great keeper).
- **Defensive heatmap**: where the team won the ball / defended. High
  concentration near the opponent goal = high press; deep = low block.
- **Progressive passes**: line density into the final third shows how a
  team advances the ball; the final-third split (L/C/R) shows channel
  preference.
- **Stats bars**: center-out bars; longer bar = team's share of that stat.
  PPDA reads inverted (lower is better), so a shorter home bar there is
  *good* for the home team.
