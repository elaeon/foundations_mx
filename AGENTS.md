---
name: Setup Agent
description: "Handles project setup and initialization. Use when: user types 'setup', or 'how do I set up this project'"
---

# Setup Agent

This agent provides guided setup instructions for the Mexico Foundations & Trusts Visualizer project.

## Setup Instructions

When a user requests setup assistance, follow these steps in order:

### 1. Install Dependencies
Run the UV package manager to install all project dependencies:

```bash
uv sync
```

This installs the Python environment with all required packages.

### 2. Configure Environment Variables
Create a `.env` file in the project root with your OpenRouter API key:

```
OPENROUTER_API_KEY=your_key_here
```

This key is required for the LLM-powered scoring pipeline.

### 3. Download and Prepare Data
Visit the [foundations dataset on Zenodo](https://zenodo.org/records/19498457) and download the file fundations.tar.gz.

The dataset contains over 10,000 files, so I recommend copying only a subset into `data/2024/` (create this folder at the same level as the `site` folder).

**Tip:** Check `foundations.csv` column "ref" to see which foundation files are used in the visualization.

### 4. Generate Initial Data Files
Run the data pipeline scripts in this order:

```bash
# Generate CSV summary from files in data/2024
uv run python make_csv.py

# Generate Markdown from Excel
uv run python process.py

# Generate foundations.json file
uv run python parse_foundations.py
```

### 5. Score Foundations (Optional)
Score foundations for AI exposure using the LLM pipeline:

```bash
# Score all foundations
uv run python score.py

# Test specific foundations
uv run python score.py --test [RFC_1,...] --model [MODEL_NAME]

# Process a subset by index range
uv run python score.py --start [INDEX] --end [INDEX]

# Add specific foundations
uv run python score.py --add [RFC_1,...]
```

### 6. Build Website Data
Merge CSV stats and AI exposure scores into the website data:

```bash
uv run python build_site_data.py
```

### 7. View the Project Locally
Start a local web server to view the interactive treemap visualization:

```bash
cd site && python -m http.server 8000
```

Open your browser and navigate to `http://localhost:8000` to see the visualization.

## Key Project Files

- `foundations.json` — Master list of 10,000+ foundations & trusts with RFC and names
- `foundations.csv` — Summary statistics
- `scores.json` — AI exposure scores with rationales
- `markdown/` — Clean Markdown versions of each foundation
- `site/` — Static website with treemap visualization

## Quick Reference

| Task | Command |
|------|---------|
| Install dependencies | `uv sync` |
| Generate CSV summary | `uv run python make_csv.py` |
| Generate Markdown | `uv run python process.py` |
| Generate foundations.json | `uv run python parse_foundations.py` |
| Score foundations | `uv run python score.py` |
| Build website data | `uv run python build_site_data.py` |
| Serve site locally | `cd site && python -m http.server 8000` |

## Notes

- The project requires an OpenRouter API key for LLM scoring functionality
- Data subset recommendation: Start with a small set of foundations for testing
- Check `foundations.json` to find RFC codes for specific foundations
- The visualization uses one color layer for risk exposure
