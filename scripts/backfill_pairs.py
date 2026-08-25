#!/usr/bin/env python3
"""Backfill pairs whose repos failed the license gate during stage A.

Reads data/matched_pairs.csv + data/metrics_raw.csv, finds pairs where either
arm has status != ok, and replaces them with unused pool repos from the SAME
stratum (loc_band x year x star band). If no exact-stratum repo exists on one
side, relaxes to an adjacent star band within the same loc_band and year
(relaxation recorded in a `relaxed` column).

Deterministic: seeded RNG (default seed = original matching seed + 1).
Writes data/matched_pairs_v2.csv; the original matched_pairs.csv is untouched.
"""
import argparse
import csv
import random

OK_LICENSES = {
    "mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause",
    "gpl-3.0", "mpl-2.0", "unlicense", "isc", "lgpl-3.0",
}
STAR_BANDS = ["0-5", "6-50", "51-500"]


def star_band(n):
    n = int(n)
    return "0-5" if n <= 5 else ("6-50" if n <= 50 else "51-500")


def load(path, lic_field="license"):
    out = []
    for r in csv.DictReader(open(path)):
        if r.get("loc_status") == "ok" and r.get(lic_field, "").lower() in OK_LICENSES:
            out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="data/matched_pairs.csv")
    ap.add_argument("--metrics", default="data/metrics_raw.csv")
    ap.add_argument("--ai", default="data/ai_loc.csv")
    ap.add_argument("--controls", default="data/controls_loc.csv")
    ap.add_argument("--seed", type=int, default=20260824)
    ap.add_argument("--out", default="data/matched_pairs_v2.csv")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    pairs = list(csv.DictReader(open(args.pairs)))
    status = {r["repo"]: r["status"] for r in csv.DictReader(open(args.metrics))}

    used_ai = {p["ai_repo"] for p in pairs}
    used_ctrl = {p["ctrl_repo"] for p in pairs}

    ai_pool = [r for r in load(args.ai) if r["full_name"] not in used_ai]
    ctrl_pool = [r for r in load(args.controls) if r["full_name"] not in used_ctrl]

    def index(pool):
        idx = {}
        for r in pool:
            key = (r["loc_band"], r["created"][:4], star_band(r["stars"]))
            idx.setdefault(key, []).append(r)
        return idx

    ai_idx, ctrl_idx = index(ai_pool), index(ctrl_pool)
    take_ai, take_ctrl = set(), set()

    def pick(idx, key, taken):
        pool = [r for r in idx.get(key, []) if r["full_name"] not in taken]
        if not pool:
            return None, False
        # prefer same band; else adjacent star bands, same loc+year
        lb, yr, sb = key
        si = STAR_BANDS.index(sb)
        for cand_sb in [sb] + [b for d in (1,) for b in
                               (STAR_BANDS[si - 1], STAR_BANDS[si + 1]) if 0 <= STAR_BANDS.index(b) < len(STAR_BANDS)]:
            sub = [r for r in idx.get((lb, yr, cand_sb), []) if r["full_name"] not in taken]
            if sub:
                pick_ = rng.choice(sub)
                return pick_, cand_sb != sb
        return None, False

    out_rows, still_missing = [], []
    for p in pairs:
        ai_ok = status.get(p["ai_repo"]) == "ok"
        c_ok = status.get(p["ctrl_repo"]) == "ok"
        if ai_ok and c_ok:
            out_rows.append({**p, "relaxed": ""})
            continue
        key = tuple(p["stratum"].split("|"))
        relaxed = []
        if not ai_ok:
            rep, rel = pick(ai_idx, key, take_ai)
            if rep is None:
                still_missing.append(p["ai_repo"])
                continue
            take_ai.add(rep["full_name"])
            if rel:
                relaxed.append(f"ai-starband:{rep['full_name']}")
            p = {**p, "ai_repo": rep["full_name"], "ai_loc": rep["src_loc"],
                 "ai_stars": rep["stars"], "ai_year": rep["created"][:4],
                 "ai_evidence": rep.get("evidence", "")}
        if not c_ok:
            rep, rel = pick(ctrl_idx, key, take_ctrl)
            if rep is None:
                still_missing.append(p["ctrl_repo"])
                continue
            take_ctrl.add(rep["full_name"])
            if rel:
                relaxed.append(f"ctrl-starband:{rep['full_name']}")
            p = {**p, "ctrl_repo": rep["full_name"], "ctrl_loc": rep["src_loc"],
                 "ctrl_stars": rep["stars"], "ctrl_year": rep["created"][:4]}
        out_rows.append({**p, "relaxed": ";".join(relaxed)})

    fields = list(out_rows[0].keys())
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    print(f"kept {sum(1 for r in out_rows if not r['relaxed'] and r['ai_repo'] in used_ai)} unchanged; "
          f"wrote {len(out_rows)} pairs -> {args.out}")
    print(f"replaced AI arms: {len(take_ai)} | replaced ctrl arms: {len(take_ctrl)}")
    print(f"unfillable (dropped): {len(still_missing)}")
    for m in still_missing:
        print("  DROP", m)


if __name__ == "__main__":
    main()
