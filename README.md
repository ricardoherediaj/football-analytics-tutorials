# football-analytics-tutorials
Open-source tutorials and code snippets for football analytics

## Quick Start with uv

### Prerequisites

First, install [uv](https://docs.astral.sh/uv/getting-started/installation/), a fast Python package manager:

```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

### Setup

1. Clone the repository:
```bash
git clone https://github.com/ricardoheredia/football-analytics-tutorials.git
cd football-analytics-tutorials
```

2. Install dependencies:
```bash
uv sync
```

3. Activate the environment and start Jupyter:
```bash
uv run jupyter notebook
```

Now you can open and run the notebooks in the `notebooks/` folder!

## What's Included

- **Match event data** - Player actions, passes, shots with coordinates
- **Expected Goals (xG)** and **Expected Threat (xT)** models
- **Interactive dashboards** for match analysis
- **Web scraping** tutorials for football data

## Notebooks

- `notebooks/match_dashboard_template.ipynb` - Create comprehensive match dashboards
- `notebooks/cwc_scraping_test.ipynb` - Web scraping for football data
