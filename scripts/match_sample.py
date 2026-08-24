#!/usr/bin/env python3
"""Phase 2 of matching: stratified 1:1 pairing of AI repos with controls.

Strata: (loc_band x creation year x star band) per docs/control-group-criteria.md.
Star bands: 0-5, 6-50, 51-500. Seeded RNG; every draw recorded for reproducibility.

AI sample selection: prioritize bot-evidence repos, then readme-declaration,
then query-only fills — until TARGET per arm.

Usage:
    python3 scripts/match_sample.py \
        --ai data/ai_loc.csv --controls data/controls_loc.csv \
        --target 50 --seed 24070145 --out data/matched_pairs.csv
"""
import argparse
import csv
import random


def star_band(n):
    n = int(n)
    if n <= 5:
        return "0-5"
    if n <= 50:
        return "6-50"
    return "51-500"


def year(created):
    return created[:4]


EVIDENCE_RANK = {"bot": 0, "readme": 1, "query-only": 2}


def ai_tier(row):
    ev = row.get("evidence", "")
    if ev.startswith("bot-contributor"):
        return "bot"
    if ev == "readme-declaration":
        return "readme"
    return "query-only"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai", required=True)
    ap.add_argument("--controls", required=True)
    ap.add_argument("--target", type=int, default=50)
    ap.add_argument("--seed", type=int, default=24070145)
    ap.add_argument("--out", default="data/matched_pairs.csv")
    args = ap.parse_args()

    rng = random.Random(args.seed)

    ai = [r for r in csv.DictReader(open(args.ai))
          if r.get("loc_status") == "ok"]
    ctrl = [r for r in csv.DictReader(open(args.controls))
            if r.get("loc_status") == "ok"]

    # AI arm: rank by evidence tier then stable key; take top --target
    ai.sort(key=lambda r: (EVIDENCE_RANK[ai_tier(r)], r["full_name"]))
    # index controls by stratum
    strata = {}
    for c in ctrl:
        key = (c["loc_band"], year(c["created"]), star_band(c["stars"]))
        strata.setdefault(key, []).append(c)

    # walk ranked list, pairing each repo whose stratum has an available control
    pairs, attrition = [], []
    used_ctrl = set()
    for a in ai:
        if len(pairs) >= args.target:
            break
        key = (a["loc_band"], year(a["created"]), star_band(a["stars"]))
        pool = [c for c in strata.get(key, []) if c["full_name"] not in used_ctrl]
        if not pool:
            attrition.append((a["full_name"], "empty-stratum", key))
            continue
        pick = rng.choice(pool)
        used_ctrl.add(pick["full_name"])
        pairs.append({
            "stratum": "|".join(key),
            "ai_repo": a["full_name"],
            "ai_loc": a["src_loc"],
            "ai_stars": a["stars"],
            "ai_year": year(a["created"]),
            "ai_evidence": a.get("evidence", ""),
            "ctrl_repo": pick["full_name"],
            "ctrl_loc": pick["src_loc"],
            "ctrl_stars": pick["stars"],
            "ctrl_year": year(pick["created"]),
            "seed": args.seed,
        })

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pairs[0].keys()) if pairs else ["stratum"])
        w.writeheader()
        w.writerows(pairs)

    print(f"AI pool: {len(ai)} | matched pairs: {len(pairs)} | attrition: {len(attrition)}")
    for name, why, key in attrition:
        print(f"  DROPPED {name} ({why}) stratum={key}")
    tiers = {}
    for p in pairs:
        t = ai_tier({"evidence": p["ai_evidence"]})
        tiers[t] = tiers.get(t, 0) + 1
    print("pair evidence mix:", tiers)


if __name__ == "__main__":
    main()
