import argparse
from pathlib import Path
import os
import json
import httpx
import time
from dotenv import load_dotenv

load_dotenv()


DEFAULT_MODEL = "qwen/qwen3.6-plus:free"
OUTPUT_FILE = "scores.json"
API_URL = "https://openrouter.ai/api/v1/chat/completions"


SYSTEM_PROMPT = """\
You are an expert analyst evaluating how fundations and trusts efficiency manage
their resources, also you have to inspect and decide if they are diverting money or doing
activities in laundring money.
You will be given a detailed description of an trust from the mexican IRS (SAT), so you have to
manage some variables names and descriptions in Spanish.

Rate the risk's overall **laundry money and efficiency management** on a scale from 0 to 1, 
where 0 is low risk / hight efficiency and 1 is highest risk / low efficiency.

Laundry Money measures: how are manage the resources? Consider efficiency \
risk, coherence and anomalies like in the structured model Fundation Risk & Efficiency Score (FRES).

Keys signals are operative efficiency (E), financial risk (R), internal coherence (C) and anomaly risk (A)
so you can use a stadistical model to get a good value, so use Z-score if is possible.
Usually are this variables are weigthed FRES=0.3E+0.25R+0.25C+0.2A, but you are free to adjust or update this weights if 
the data is viable. You also can build derivates variables like liquidity, leverage and weight of the assets.
You have to be very critic no matter the fundation's objetives or misions.
Also, check concisely the history of the board of directors (organo de gobierno).

Use these anchors to calibrate your score:

- **.8–1: Very Hight exposure.** The fundation or trust is in hight risk or low efficiency.

- **.6–.79: Hight exposure.** They are weakness or inconsistencies that could lead to a mayor problem \
and should be resolved.

- **.4–.59: Moderate exposure.** They have room to improvement efficiency that should be fixed. The operation could have some
data manipulation or the board members could be suppliers.

- **.2–.39: Low exposure.** Low financial risk, expenses are well distributed and low sign of bad management.

- **0–.19: Very Low exposure.** Hight efficiency and the lowest risk of inconsistencies without anomalies or suspiciuos variables \
or data manipulation.


Respond with ONLY a JSON object in this exact format, no other text:
{
  "exposure": <0-1>,
  "rationale": "<2-3 sentences explaining the key factors>"
}\
"""


def score_occupation(client, text, model):
    """Send one occupation to the LLM and parse the structured response."""
    response = client.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.2,
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # remove first line
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    return json.loads(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=False, default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, required=False, default=0)
    parser.add_argument("--end", type=int, required=False, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--force", action="store_true",
                        help="Re-score even if already cached")
    parser.add_argument("--test", type=str, required=False, nargs='+', default=[])
    parser.add_argument("--add", type=str, required=False, nargs='+', default=[])
    parser.add_argument("--year", required=False, default=2024, type=int)

    args = parser.parse_args()
    with open("fundations.json") as f:
        fundations = json.load(f)
    
    scores = {}
    if args.test:
        rfc_list = args.test
    elif args.add:
        rfc_list = args.add
    else:
        rfc_list = []

    if len(rfc_list) > 0:
        subset = []
        for fund in fundations:
            if fund["rfc"] in rfc_list:
                subset.append(fund)
    else:
        subset = fundations[args.start:args.end]

    if not args.test:
        # Load existing scores
        if os.path.exists(OUTPUT_FILE) and not args.force:
            with open(OUTPUT_FILE) as f:
                for entry in json.load(f):
                    scores[entry["rfc"]] = entry
    
    print(f"Scoring {len(subset)} occupations with {args.model}")
    print(f"Already cached: {len(scores)}")

    errors = []
    client = httpx.Client()

    for i, fundation in enumerate(subset):
        rfc = fundation["rfc"]

        if rfc in scores:
            continue

        md_path = f"markdown/{args.year}/{rfc}.md"
        if not os.path.exists(md_path):
            print(f"  [{i+1}] SKIP {rfc} (no markdown)")
            continue

        with open(md_path) as f:
            text = f.read()

        print(f"  [{i+1}/{len(subset)}] {fundation['name']}...", end=" ", flush=True)

        try:
            result = score_occupation(client, text, args.model)
            scores[rfc] = {
                "rfc": rfc,
                "name": fundation["name"],
                "model": args.model,
                **result,
            }
            print(f"exposure={result['exposure']}")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(rfc)

        # Save after each one (incremental checkpoint)
        if not args.test:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(list(scores.values()), f, indent=2)
        else:
            print(scores)

        if i < len(subset) - 1:
            time.sleep(args.delay)
    
    client.close()

    print(f"\nDone. Scored {len(scores)} fundations, {len(errors)} errors.")
    if errors:
        print(f"Errors: {errors}")

    # Summary stats
    vals = [s for s in scores.values() if "exposure" in s]
    if vals:
        avg = sum(s["exposure"] for s in vals) / len(vals)
        by_score = {}
        for s in vals:
            bucket = s["exposure"]
            by_score[bucket] = by_score.get(bucket, 0) + 1
        print(f"\nAverage exposure across {len(vals)} fundation: {avg:.1f}")
        print("Distribution:")
        for k in sorted(by_score):
            print(f"  {k}: {'█' * by_score[k]} ({by_score[k]})")


if __name__ == "__main__":
    main()