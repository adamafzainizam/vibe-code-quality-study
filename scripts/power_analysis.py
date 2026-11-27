#!/usr/bin/env python3
"""What can n=46 actually detect? Minimum detectable effect + CIs on d_z.

The study's headline is a set of p-values above 0.10. A p-value above 0.10 with
46 pairs rules out a large difference and nothing else; this script quantifies
that instead of leaving it to the reader.

Two numbers per metric:
  - d_z, the standardised mean of the within-pair difference (mean/sd), with a
    bootstrap 95% CI. This is the effect the study can rule in or out.
  - the minimum detectable effect (MDE) at 80% power for a two-sided Wilcoxon
    signed-rank test at n=46, by simulation, so the CI can be read against it.

It also answers the obvious follow-up: how many pairs would be needed at 80%
power for d_z = 0.3 and 0.4.

Usage:
    .venv/bin/python scripts/power_analysis.py \
        --pairs data/paired_stats.csv --out data/power_analysis.txt
"""
import argparse
import csv

import numpy as np
from scipy import stats

METRICS = [
    "sloc", "comment_ratio", "docstring_density",
    "cc_mean", "cc_max", "pct_cc_gt_10",
    "mi_mean", "mi_min",
    "lizard_avg_ccn", "lizard_max_ccn", "lizard_avg_nloc",
    "avg_tokens_per_func", "docstring_viols_per_kloc",
]
RNG = np.random.default_rng(20260827)
REPS = 4000
ALPHA = 0.05


def sim_power(n, d_z, reps=REPS):
    """Power of a two-sided Wilcoxon signed-rank test on n paired diffs."""
    hits = 0
    for _ in range(reps):
        # x, y correlated normals whose difference has mean d_z and sd 1
        base = RNG.standard_normal(n)
        noise = RNG.standard_normal(n)
        diff = d_z + noise  # equivalent, and what the test actually sees
        try:
            p = stats.wilcoxon(diff).pvalue
        except ValueError:
            continue
        if p < ALPHA:
            hits += 1
    return hits / reps


def mde(n, lo=0.0, hi=1.2, tol=0.01):
    """Smallest d_z reaching 80% power, by bisection."""
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if sim_power(n, mid) >= 0.80:
            hi = mid
        else:
            lo = mid
    return hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="data/paired_stats.csv")
    ap.add_argument("--out", default="data/power_analysis.txt")
    ap.add_argument("--boot", type=int, default=4000)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.pairs)))
    n = len(rows)
    out = []
    A = out.append

    A("=== Sensitivity of the paired analysis ===")
    A("")
    A(f"Pairs: n={n}. Two-sided alpha=0.05. d_z = mean within-pair difference /")
    A("its sd; positive means the AI-assisted repo scored higher.")
    A("")

    header = f"{'metric':28s} {'d_z':>7s} {'95% CI':>18s} {'Wil p':>8s}"
    A(header)
    A("-" * len(header))

    det = {}
    for m in METRICS:
        d = np.array([float(r[f"delta_{m}"]) for r in rows])
        if np.allclose(d, 0):
            A(f"{m:28s} {'n/a':>7s} {'(no variation)':>18s} {'1.0000':>8s}")
            continue
        dz = d.mean() / d.std(ddof=1)
        boots = np.array([
            (lambda s: s.mean() / s.std(ddof=1))(
                RNG.choice(d, size=len(d), replace=True)) for _ in range(args.boot)])
        lo, hi = np.percentile(boots, [2.5, 97.5])
        p = stats.wilcoxon(d).pvalue if not np.allclose(d, 0) else 1.0
        det[m] = (dz, lo, hi, p)
        A(f"{m:28s} {dz:7.3f} {f'[{lo:+.3f}, {hi:+.3f}]':>18s} {p:8.4f}")

    A("")
    A("=== Minimum detectable effect (Wilcoxon, 80% power) ===")
    A("")
    mde46 = mde(n)
    A(f"At n={n}: |d_z| >= {mde46:.2f} is detectable at 80% power.")
    for dz_probe in (0.2, 0.3, 0.5):
        A(f"  power at d_z={dz_probe:.1f}: {sim_power(n, dz_probe):.0%}")
    out_small = [m for m, (dz, lo, hi, p) in det.items() if hi < mde46 and lo > -mde46]
    A("")
    A(f"Metrics whose whole CI sits inside the undetectable band (|CI| < {mde46:.2f}),")
    A("so the study cannot distinguish them from no difference at all:")
    A("  " + (", ".join(out_small) if out_small else "(none)"))
    A("")
    A("=== Pairs needed at 80% power ===")
    A("")
    for dz in (0.3, 0.4, 0.5):
        lo, hi = 10, 400
        while hi - lo > 2:
            mid = (lo + hi) // 2
            if sim_power(int(mid), dz, reps=1200) >= 0.80:
                hi = int(mid)
            else:
                lo = int(mid)
        A(f"  d_z={dz:.1f}: about {hi} pairs")

    text = "\n".join(out) + "\n"
    with open(args.out, "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
