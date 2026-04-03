"""
Build a compact JSON for the website by merging CSV stats with fundations scores.

Reads occupations.csv (for stats) and scores.json (for scores).
Writes site/data.json.

Usage:
    uv run python build_site_data.py
"""

import csv
import json
import os


def main():
    with open("scores.json", "r") as f:
        scores_list = json.load(f)
    scores = {s["rfc"]: s for s in scores_list}

    with open("fundations.csv", "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Merge
    data = []
    for row in rows:
        rfc = row["Rfc"]
        score = scores.get(rfc, {})
        if "exposure" not in score: continue
        data.append({
            "title": row["Razón social"],
            "rfc": rfc,
            "category": row["Rubro"],
            "patrimony": int(row["Patrimonio"]),
            "workforce": int(row["Plantilla laboral"]),
            "volunteers": int(row["Voluntarios"]),
            "wages": int(row["Monto salarios"]),
            "beneficiaries": int(row["Número de beneficiados"]),
            "exposure": round(score.get("exposure")*10),
            "exposure_rationale": score.get("rationale"),
            "url": row.get("ref", ""),
        })

    
    os.makedirs("site", exist_ok=True)
    with open("site/data.json", "w") as f:
        json.dump(data, f)

    print(f"Wrote {len(data)} fundations to site/data.json")
    total_benef = sum(d["beneficiaries"] for d in data if d["beneficiaries"])
    print(f"Total beneficiaries represented: {total_benef:,}")


if __name__ == "__main__":
    main()
