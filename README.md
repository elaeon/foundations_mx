# Mexico Fundations & Trusts Visualizer

A research tool for visually exploring transparency in Fundations Statistics [Donatarias consulta pública](https://eu2-por-pro-don-net-cons.azurewebsites.net/Consulta/Acceso?ReturnUrl=%2FConsulta%2FTransparencia) data. This is not a report, a paper, or a serious economic publication — it is a development tool for exploring Fundations & Trust data visually.

**Live demo: **

## What's here

The Site **10017 fundations & trusts** in many years, with detailed data on donatios. We (eventually) scraped all of it and built an interactive treemap visualization where each rectangle's **area** is proportional to total money and **color** shows the selected metric.

## LLM-powered coloring

The repo includes scrapers, parsers, and a pipeline for writing custom LLM prompts to score and color fundations by any criteria. You write a prompt, the LLM scores to evaluate fundations activity, and the treemap colors accordingly. But you could write a different prompt for any question. See `score.py` for the prompt and scoring pipeline.

**What "Fundations MX analisys" is NOT:**
- It does **not** an auditor or an stadistical method specifically to analize money laundring or finantial risks on trusts.
- It does **not** account for network analisys u other method to identify donations flow.
- The scores are rough LLM estimates, not rigorous model analisys.

## Data pipeline

1. **Scrape** (`scrape.py`) — Not yet implemented.
2. **Parse** (`parse_fundations.py`, `process.py`) — Converts Excel into clean json (fundations.json) or Markdown files in `markdown/`.
3. **Tabulate** (`make_csv.py`) — Extracts structured fields into `fundations.csv`.
4. **Score** (`score.py`) — Sends each fundation's Markdown description to an LLM with a scoring rubric. Each fundation gets a score from 0-1 with a rationale. Results saved to `scores.json`. Fork this to write your own prompts.
5. **Build site data** (`build_site_data.py`) — Merges CSV stats and AI exposure scores into a compact `site/data.json` for the frontend.
6. **Website** (`site/index.html`) — Interactive treemap visualization with four color layers: BLS Outlook, Median Pay, Education, and Digital AI Exposure.

## Key files

| File | Description |
|------|-------------|
| `fundations.json` | Master list of 10017 fundations & trusts with rfc, state, name |
| `fundations.csv` | Summary stats |
| `scores.json` | AI exposure scores (0-1) with rationales for (eventually) all 10017 fundations |
| `markdown/` | Clean Markdown versions of each fundation file |
| `site/` | Static website (treemap visualization) |


## Setup

```
uv sync
uv run playwright install chromium
```

Requires an OpenRouter API key in `.env`:
```
OPENROUTER_API_KEY=your_key_here
```

## Usage

```bash

# Generate Markdown from Excel
uv run python process.py

# Generate CSV summary
uv run python make_csv.py

# Score AI exposure (uses OpenRouter API)
uv run python score.py

# Build website data
uv run python build_site_data.py

# Serve the site locally
cd site && python -m http.server 8000
```
