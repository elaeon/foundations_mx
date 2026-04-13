# Mexico Foundations & Trusts Visualizer

A research tool for visually exploring transparency in foundations Statistics [Donatarias consulta pública](https://eu2-por-pro-don-net-cons.azurewebsites.net/Consulta/Acceso?ReturnUrl=%2FConsulta%2FTransparencia) data. This is not a report, a paper, or a serious economic publication — it is a development tool for exploring foundations & Trust data visually.

**Live demo: [foundations_mx](https://elaeon.github.io/foundations_mx/)**

## What's here

This repo **Mexico Foundations & Trusts** review detailed data on donatios. We scraped an small portion of all of it and built an interactive treemap visualization where each rectangle's **area** is proportional to beneficiaries and **color** shows the exposure metric.

## LLM-powered coloring

The repo includes scrapers, parsers, and a pipeline for writing custom LLM prompts to score and color foundations by any criteria. You write a prompt, the LLM scores to evaluate foundations activity, and the treemap colors accordingly. But you could write a different prompt for any question. See `score.py` for the prompt and scoring pipeline.

**What "Foundations MX analisys" is NOT:**
- It does **not** an auditor or an stadistical method specifically to analize money laundring or finantial risks on trusts.
- It does **not** account for network analisys u other method to identify donations flow.
- The scores are rough LLM estimates, not rigorous model analisys.

## Data pipeline

1. **Scrape** (`scrape.py`) — Not yet implemented.
2. **Parse** (`parse_foundations.py`, `process.py`) — Converts Excel into clean json (foundations.json) or Markdown files in `markdown/`.
3. **Tabulate** (`make_csv.py`) — Extracts structured fields into `foundations.csv`.
4. **Score** (`score.py`) — Sends each foundation's Markdown description to an LLM with a scoring rubric. Each foundation gets a score from 0-1 with a rationale. Results saved to `scores.json`. Fork this to write your own prompts.
5. **Build site data** (`build_site_data.py`) — Merges CSV stats and AI exposure scores into a compact `site/data.json` for the frontend.
6. **Website** (`site/index.html`) — Interactive treemap visualization with four color layers: BLS Outlook, Median Pay, Education, and Digital AI Exposure.

## Key files

| File | Description |
|------|-------------|
| `foundations.json` | Master list of more than 10,000 foundations & trusts with rfc and name |
| `foundations.csv` | Summary stats |
| `scores.json` | AI exposure scores (0-1) with rationales for an small subset of foundations |
| `markdown/` | Clean Markdown versions of each foundation file |
| `site/` | Static website (treemap visualization) |


## Setup

```
uv sync
```

Requires an OpenRouter API key in `.env`:
```
OPENROUTER_API_KEY=your_key_here
```

Download the [dataset](https://zenodo.org/records/19498457) 
into a folder named "data" in the same level as the folder "site"
uncompress it and rename the folder to 2024

## Usage

```bash

# Generate CSV summary (foundations.csv) from files inside of data/2024
uv run python make_csv.py

# Generate Markdown from Excel (this will make a folder named markdown)
uv run python process.py

# Generate foundations.json file
uv run python parse_foundations.py

# Score AI exposure (uses OpenRouter API)
uv run python score.py

# Build website data
uv run python build_site_data.py

# Serve the site locally
cd site && python -m http.server 8000

# Test some foundations with a specific model
uv run python score.py --test [RFC_1,...] --model [MODEL_NAME]

# You can run a subset with:
uv run python score.py --start [INDEX] --end [INDEX]
or
uv run python score.py --add [RFC_1,...]

```
Inside foundations.json you can consult the RFC and foundations names.
