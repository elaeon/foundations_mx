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

1. **Fetch** (`fetch.py`) not really need it if you download the foundation dataset.
2. **Parse** (`parse_foundations.py`, `process.py`) — Converts Excel into clean json (foundations.json) or Markdown files in `markdown/`.
3. **Tabulate** (`make_csv.py`) — Extracts structured fields into `foundations.csv`.
4. **Score** (`score.py`) — Sends each foundation's Markdown description to an LLM with a scoring rubric. Each foundation gets a score from 0-1 with a rationale. Results saved to `scores.json`. Fork this to write your own prompts.
5. **Build site data** (`build_site_data.py`) — Merges CSV stats and AI exposure scores into a compact `site/data.json` for the frontend.
6. **Website** (`site/index.html`) — Interactive treemap visualization with color layer for risk exposure.

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

Download the [foundations dataset](https://zenodo.org/records/19498457) 
This dataset contains more than 10,000 files, so I recommend you to copy only
a subset of these into a folder named "data/2024" in the same level as the folder "site".
You can look in foundations.csv, the column "ref" has the file names used in this visualization.


## Agent setup
Or in your agent code type "setup" to manage the previous steps.

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

## Analysis (`analyze.py`)

`analyze.py` explores the donation data as a **directed graph** of money flows between
RFCs (donor → recipient, with cash `monto_efectivo` and in-kind `monto_especie` on each
edge). It is a screening aid for spotting suspicious relations — **not** an auditor; every
pattern it surfaces also has legitimate explanations and should be verified against primary
sources.

It has two subcommands: `search` and `graph`.

### `search` — keyword search + export

Finds foundations whose `Rubro`, `Misión`, or `Actividad` match a keyword, then exports
their *Destino de donativos* rows to CSV.

```bash
uv run python analyze.py search --input-file foundations_full.csv --keyword educacion
```

| Option | Description |
|--------|-------------|
| `--input-file` | **(required)** CSV with a `ref` column (e.g. `foundations_full.csv`) |
| `--keyword` | **(required)** case-insensitive substring matched against Rubro/Misión/Actividad |
| `--output` | output CSV path (default `destino_donativos.csv`) |
| `--limit N` | process only the first N matched files |

### `graph` — find suspicious donation patterns

On first run it builds the graph from the XLSX files referenced in the CSV and caches it
next to the input (e.g. `foundations_full_graph.json`); later runs load the cache. Pick a
**mode** below; default mode (no mode flag) is cycle detection.

```bash
# Whole-graph scan for the highest-value circular flows
uv run python analyze.py graph --input-file foundations_full.csv --min-amount 1000000

# Deep dive on one RFC
uv run python analyze.py graph --input-file foundations_full.csv --rfc FER001020CE1
uv run python analyze.py graph --input-file foundations_full.csv --rfc FER001020CE1 --successors
```

**Modes** (mutually exclusive; omit all for cycle detection):

| Mode | What it surfaces | Red flag |
|------|------------------|----------|
| *(none)* | **Cycles** — money that loops back to its origin, ranked by `bottleneck` (the smallest hop = how much actually circulates) | Round-tripping / circular flows |
| `--reciprocal` | Mutual-donation pairs `A↔B` ranked by round-tripped amount, with a `balance` ratio (1.0 = perfectly balanced) | Wash-style two-way exchanges |
| `--conduits` | Pass-through nodes: `in`, `out`, `retained`, `ratio = min(in,out)/max(in,out)` | Layering — money parked briefly then forwarded |
| `--clusters` | Strongly-connected groups ranked by size and `% internal money retained` | Related-party networks recycling funds internally |
| `--self-loops` | RFCs that donate to themselves, ranked by amount | Self-dealing or data artifacts |
| `--predecessors` | All RFCs that donate **into** `--rfc` (requires `--rfc`) | Who funds this entity |
| `--successors` | All RFCs that `--rfc` donates **to** (requires `--rfc`) | Where this entity's money goes |

**Common options:**

| Option | Description |
|--------|-------------|
| `--input-file` | **(required)** CSV with `ref` and `Rfc` columns |
| `--rfc RFC` | focus on one RFC; omit to scan the whole graph |
| `--min-amount PESOS` | ignore cycles/pairs/nodes/clusters below this peso amount |
| `--output FILE` | write results to a file instead of printing |
| `--force` | rebuild the graph, ignoring the cache |
| `--limit N` | build from only the first N files (skips cache write) |

**Cycle-mode options:**

| Option | Description |
|--------|-------------|
| `--max-cycles N` | max cycles to return (default 100; `0` = unlimited) |
| `--max-depth N` | max cycle length in hops (default 8; `0` = unlimited) |
| `--shortest` | return only the shortest cycles |
| `--greater-than N` | only cycles with more than N nodes (e.g. `1` drops self-loops) |
| `--distinct-prev` | shortest cycle per distinct direct predecessor (requires `--rfc`) |

**Conduit-mode option:**

| Option | Description |
|--------|-------------|
| `--ratio R` | keep only nodes with `min(in,out)/max(in,out) >= R` (default `0` = no filter; e.g. `0.9` for near-perfect pass-throughs) |
