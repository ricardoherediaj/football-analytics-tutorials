# Metric Definitions & Interpretation

Reference for every chart in the post-match team report. Everything is
computed on the fly from the scraped WhoScored event stream and FotMob
payload — nothing is hardcoded per match.

## Coordinate conventions

- **WhoScored events** arrive in a 0-100 space and are scaled to a **UEFA
  105x68 pitch** (`x*1.05`, `y*0.68`) — the Post-Match-Report-2.0 blueprint
  convention. In the raw data both teams attack toward x=105; the **away
  team's axes are inverted** for display and **home shots are flipped** in
  the shot map so both teams attack the correct goal.
- **FotMob shots** are 0-100 percentages of the pitch; xG/xGOT are taken
  from `expectedGoals` / `expectedGoalsOnTarget`.
- **Goal-mouth coordinates** (`goalMouthY`, `goalMouthZ`) are 0-100
  percentages of the goal mouth (50 = center; Z 0 = ground, 100 = crossbar)
  and are normalized into the goal frames of the GK-saves chart.

## Data pipeline

1. Flatten events (display names, cumulative minutes).
2. **Synthesize carries** between same-team touches that leave a gap
   (3-60 m, 1-10 s) — powers progressive carries, final-third entries, box
   entries and xT on carries.
3. **Possession chains** (`possession_id`) — powers high-turnover analysis.
4. **xT assignment** from the 12x8 grid for successful passes/carries.
5. Progressive pass/carry distances: distance gained toward the home goal
   `(105, 34)`; a pass/carry is progressive when it gains ≥ 9.11 m and
   starts outside the defensive third (x ≥ 35).

## Chart-by-chart

### Figure 1 — Team report

| Chart | Read |
|-------|------|
| **Passing network** | Nodes = median positions, shirt numbers inside; circle = starter, square = sub; line width/alpha ∝ completed-pass volume. Dashed line = median pass height; dotted lines = centre-back (defensive) and top-2-forward (attacking) line heights; shaded zone = between them. Verticality % = how direct the passing is (0-100). |
| **Shot map** | Football markers = goals (green edge), hatched = saved, filled = posts, empty = misses; big chances get larger markers. The bar strip below compares Goals / xG / xGOT / Shots / On Target / BigChance / BigC.Miss / xG-per-shot / Avg. distance. |
| **Defensive block** | KDE heatmap of tackles/interceptions/recoveries/clearances/etc.; nodes sized by action count with shirt numbers; dashed line = average defensive-action height; compactness % = `1 - (forward line − back line)/105`. |
| **GK saves** | Goal-mouth view: where shots went against each keeper (hatched = saves, football = goals, orange = posts). |
| **Progressive passes** | Successful passes gaining ≥ 9.11 m toward goal from x ≥ 35, set pieces excluded; comet lines; left/center/right channel split. |
| **xT momentum** | Average xT per minute; home team plotted above zero, away below (away values negated); green-hatched markers = goals, red squares = red cards; halftime dotted line. |
| **Progressive carries** | Carries gaining ≥ 9.11 m toward goal; dashed arrows with the same channel split. |
| **Match stats** | Center-out bars: possession, field tilt, accurate passes, accurate long balls, corners, avg GK kick length, tackles won, interceptions, clearances, aerials won, PPDA. |

### Figure 2 — Zones report

| Chart | Read |
|-------|------|
| **Final-third entries** | Successful passes/carries that start before x=70 and end after; split by channel and by pass vs carry. |
| **Box entries** | Passes/carries into the opponent penalty box (x ≥ 88.5, y within box); per-channel counts in the squares. |
| **Zone 14 & half-spaces** | Passes ending in Zone 14 (central, just outside the box) = orange; half-space passes = team color. |
| **Crosses** | Passes with the Cross qualifier (corners excluded); solid arrows = accurate, faint = inaccurate. |
| **Pass end zone** | Heatmap of where each team's successful passes end (6x5 grid, % of total). |
| **High turnovers** | Ball recoveries/interceptions within 40 m of the opponent goal; star = led to goal, filled = led to shot, hollow = other. |
| **Chance creating zone** | Key-pass heatmap; violet lines = key passes, green = intentional goal assists. |
| **Congestion** | Open-play touch share per zone (6x5): >55% for a team = team color, else gray. |

## Reading the report

- **xT momentum**: bars above zero = home threat, below = away. A team that
  leads xT but loses usually underperformed in finishing.
- **PPDA** (passes per defensive action): lower = more aggressive pressing.
- **Passing network spread** shows the team's shape; a narrow mid-third
  cluster = low block.
- **Progressive pass direction** shows how the team advances; the channel
  split shows where they attack.
