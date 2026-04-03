"""Parse fundation list to extract all fundations."""

import json
from pathlib import Path
import csv

data_folder = f"data/fundations_2026.csv"
data_path = Path(data_folder)

fundations = {}

with data_path.open("r") as f:
    csv_reader = csv.DictReader(f)
    for row in csv_reader:
        if row["RFC"] not in fundations:
            fundations[row["RFC"]] = {
                "rfc": row["RFC"],
                "state": row["ENTIDAD FEDERATIVA*"],
                "name": row["DENOMINACIÓN O RAZÓN SOCIAL*"]
            }

fundations_list = list(fundations.values())
print(f"Total unique fundations: {len(fundations_list)}")
print()
print("--- First 10 fundations ---")
for row in fundations_list[:10]:
    print(f"  {row['name']}")
    print(f"    {row['rfc']}")
print("...")
print()
print("--- Last 10 fundations ---")
for row in fundations_list[-10:]:
    print(f"  {row['name']}")
    print(f"    {row['rfc']}")

# Save to JSON for further analysis
with open("fundations.json", "w") as f:
    json.dump(fundations_list, f, indent=2)

print(f"\nSaved {len(fundations_list)} fundations to fundations.json")
