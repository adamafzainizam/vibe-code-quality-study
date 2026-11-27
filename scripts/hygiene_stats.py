#!/usr/bin/env python3
"""Arm join for the hygiene measures, with paired tests and FDR control.

Reads data/hygiene_metrics.csv (arm-blind, keyed by repo) and
data/matched_pairs_v2.csv (the only file that knows the arms) and reports:

  - binary practices (tests, CI, packaging, lockfile): exact McNemar on the
    discordant pairs, which is the paired equivalent of a 2x2 test
  - rate/coverage measures: paired Wilcoxon signed-rank, median difference and
    matched-pairs rank-biserial r, the same convention as aggregate_stats.py
  - Benjamini-Hochberg q values within each family, because 14 metrics tested
    at 0.05 without correction would produce a finding out of noise alone

Usage:
    .venv/bin/python scripts/hygiene_stats.py \
        --metrics data/hygiene_metrics.csv --pairs data/matched_pairs_v2.csv \
        --out data/hygiene_stats.txt
"""
import argparse
import csv

import numpy as np
from scipy import stats

BINARY = [
    ("has_tests", "has tests"),
    ("has_ci", "has CI workflow"),
    ("has_packaging", "declares dependencies"),
    ("has_lockfile", "pins with a lockfile"),
    ("has_pyproject", "has pyproject.toml"),
]
RATES = [
    ("test_loc_ratio", "test LOC / source LOC"),
    ("n_test_funcs", "test functions"),
    ("type_hint_coverage", "annotated defs / defs"),
    ("func_docstring_coverage", "documented defs / defs"),
    ("bare_except_per_kloc", "bare except per kloc"),
    ("broad_except_per_kloc", "except Exception per kloc"),
    ("assert_per_kloc", "asserts per kloc"),
    ("print_per_kloc", "prints per kloc"),
    ("parse_fail_rate", "files that fail to parse"),
]


def bh(pvals):
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank, idx in enumerate(order[::-1], start=1):
        prev = min(prev, p[idx] * n / (n - rank + 1))
        q[idx] = prev
    return q


def rank_biserial(d):
    d = np.asarray(d, dtype=float)
    nz = d[d != 0]
    if len(nz) == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(nz))
    return float((ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", default="data/hygiene_metrics.csv")
    ap.add_argument("--pairs", default="data/matched_pairs_v2.csv")
    ap.add_argument("--out", default="data/hygiene_stats.txt")
    args = ap.parse_args()

    hyg = {r["repo"]: r for r in csv.DictReader(open(args.metrics))}
    pairs = list(csv.DictReader(open(args.pairs)))
    out = []
    A = out.append

    usable = [p for p in pairs
              if hyg.get(p["ai_repo"], {}).get("status") == "ok"
              and hyg.get(p["ctrl_repo"], {}).get("status") == "ok"]

    A("=== Engineering hygiene, paired comparison ===")
    A("")
    A(f"{len(usable)} of {len(pairs)} pairs measured. Each test is paired: the two")
    A("repos in a pair share a size band, a creation year and a star band.")
    A("")

    A("--- Practices (share of repos doing it) ---")
    A("")
    hdr = f"{'practice':26s} {'AI':>8s} {'ctrl':>8s} {'both':>5s} {'AI only':>8s} {'ctrl only':>10s} {'p (exact McNemar)':>18s}"
    A(hdr)
    A("-" * len(hdr))
    pv, names = [], []
    for key, label in BINARY:
        both = ai_only = ctrl_only = neither = 0
        for p in usable:
            a = int(float(hyg[p["ai_repo"]][key] or 0))
            c = int(float(hyg[p["ctrl_repo"]][key] or 0))
            if a and c:
                both += 1
            elif a:
                ai_only += 1
            elif c:
                ctrl_only += 1
            else:
                neither += 1
        n = len(usable)
        # exact McNemar: binomial test on the discordant pairs
        disc = ai_only + ctrl_only
        p_mc = stats.binomtest(ai_only, disc, 0.5).pvalue if disc else 1.0
        pv.append(p_mc)
        names.append(label)
        A(f"{label:26s} {f'{(both + ai_only) / n:.0%}':>8s} {f'{(both + ctrl_only) / n:.0%}':>8s} "
          f"{both:5d} {ai_only:8d} {ctrl_only:10d} {p_mc:18.4f}")
    for (key, label), q in zip(BINARY, bh(pv)):
        A(f"  q = {q:.3f}  {label}")
    A("")

    A("--- Rates and coverage (paired Wilcoxon) ---")
    A("")
    hdr = f"{'measure':28s} {'n':>3s} {'AI median':>10s} {'ctrl median':>12s} {'median diff':>12s} {'p':>8s} {'r':>7s}"
    A(hdr)
    A("-" * len(hdr))
    pv2, names2 = [], []
    for key, label in RATES:
        a = np.array([float(hyg[p["ai_repo"]][key] or 0) for p in usable])
        c = np.array([float(hyg[p["ctrl_repo"]][key] or 0) for p in usable])
        d = a - c
        if np.allclose(d, 0):
            p = 1.0
        else:
            try:
                p = stats.wilcoxon(d).pvalue
            except ValueError:
                p = 1.0
        pv2.append(p)
        names2.append(label)
        A(f"{label:28s} {len(d):3d} {np.median(a):10.3f} {np.median(c):12.3f} "
          f"{np.median(d):+12.3f} {p:8.4f} {rank_biserial(d):+7.3f}")
    for (key, label), q in zip(RATES, bh(pv2)):
        A(f"  q = {q:.3f}  {label}")
    A("")

    A("--- Hygiene score (practices present out of 4: tests, CI, packaging, lockfile) ---")
    A("")
    keys = ["has_tests", "has_ci", "has_packaging", "has_lockfile"]
    a = np.array([sum(int(float(hyg[p["ai_repo"]][k] or 0)) for k in keys) for p in usable])
    c = np.array([sum(int(float(hyg[p["ctrl_repo"]][k] or 0)) for k in keys) for p in usable])
    d = a - c
    p = stats.wilcoxon(d).pvalue if not np.allclose(d, 0) else 1.0
    A(f"  AI mean {a.mean():.2f}/4, traditional mean {c.mean():.2f}/4")
    A(f"  paired Wilcoxon p={p:.4f}, rank-biserial r={rank_biserial(d):+.3f}, n={len(d)}")
    A("")
    A("=== How to read this ===")
    A("")
    A("- Exact McNemar asks only about pairs that disagree, so a practice both arms")
    A("  always follow (or never follow) contributes nothing either way.")
    A("- q values control the false discovery rate within each family. A raw p")
    A("  below 0.05 with q above 0.10 is a lead, not a result.")
    A("- These measures are not in the study's pre-registered metric list; they are a")
    A("  second question asked of the same repos, and should be described that way.")

    text = "\n".join(out) + "\n"
    with open(args.out, "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
