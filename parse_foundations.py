"""Parse foundation list to extract all foundations."""

import json
from pathlib import Path
import csv

data_folder = f"foundations.csv"
data_path = Path(data_folder)

foundations = {}

with data_path.open("r") as f:
    csv_reader = csv.DictReader(f)
    for row in csv_reader:
        if row["Rfc"] not in foundations:
            foundations[row["Rfc"]] = {
                "rfc": row["Rfc"],
                "name": row["Razón social"]
            }

foundations_list = list(foundations.values())
print(f"Total unique foundations: {len(foundations_list)}")
print()
print("--- First 10 foundations ---")
for row in foundations_list[:10]:
    print(f"  {row['name']}")
    print(f"    {row['rfc']}")
print("...")
print()
print("--- Last 10 foundations ---")
for row in foundations_list[-10:]:
    print(f"  {row['name']}")
    print(f"    {row['rfc']}")

# Save to JSON for further analysis
with open("foundations.json", "w") as f:
    json.dump(foundations_list, f, indent=2)

print(f"\nSaved {len(foundations_list)} foundations to foundations.json")
