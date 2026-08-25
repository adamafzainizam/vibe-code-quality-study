#!/usr/bin/env python3
"""Analysis pipeline stage B: aggregate metrics into paired statistics.

Reads data/metrics_raw.csv (arm-blind per-repo metrics) and
data/matched_pairs.csv (the ONLY place the arm mapping lives — joined here,
after all measurement is done). Emits:

  data/paired_stats.csv   one row per pair: metric values for both arms + deltas
  data/summary.txt        human-readable summary: n analyzed/skipped/error,
                          per-metric paired Wilcoxon signed-rank + Wilcoxon /
                          paired t, medians per arm, effect size (matched-pairs
                          rank-biserial r)

Usage:
    .venv/bin/python scripts/aggregate_stats.py \
        --metrics data/metrics_raw.csv --pairs data/matched_pairs.csv
"""
import argparse
import csv

from scipy import stats

METRICS = [
    "sloc", "comment_ratio", "docstring_density",
    "cc_mean", "cc_max", "pct_cc_gt_10",
    "mi_mean", "mi_min",
    "lizard_avg_ccn", "lizard_max_ccn", "lizard_avg_nloc",
    "avg_tokens_per_func",
    "docstring_viols_per_kloc",
]

DERIVED = {
    # name -> (numerator, denominator) computed from base fields
    "comment_ratio": ("comment_lines", "sloc"),
    "docstring_density": ("docstring_lines", "sloc"),
}


def derived_value(row, name):
    if name in DERIVED:
        num, den = DERIVED[name]
        try:
            n_, d_ = float(row[num]), float(row[den])
            return n_ / d_ if d_ else ""
        except (ValueError, KeyError):
            return ""
    v = row.get(name, "")
    try:
        return float(v)
    except ValueError:
        return ""


def fmt(v):
    return f"{v:.4g}" if isinstance(v, float) else str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", default="data/metrics_raw.csv")
    ap.add_argument("--pairs", default="data/matched_pairs.csv")
    ap.add_argument("--out-pairs", default="data/paired_stats.csv")
    ap.add_argument("--out-summary", default="data/summary.txt")
    args = ap.parse_args()

    metrics = {r["repo"]: r for r in csv.DictReader(open(args.metrics))}
    pairs = list(csv.DictReader(open(args.pairs)))

    # ---- status counts ----
    counts = {}
    for r in metrics.values():
        key = r["status"].split(":")[0] + (":" + r["status"].split(":")[1]
                                           if ":" in r["status"] else "")
        counts[key] = counts.get(key, 0) + 1

    lines = ["=== Pair-level analysis ===\n"]
    lines.append("Repo statuses: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    usable_pairs = []
    for p in pairs:
        ai, ctrl = metrics.get(p["ai_repo"]), metrics.get(p["ctrl_repo"])
        if not ai or not ctrl:
            continue
        if ai["status"] != "ok" or ctrl["status"] != "ok":
            continue
        usable_pairs.append(p)

    lines.append(f"Complete pairs (both arms analyzed): {len(usable_pairs)}/{len(pairs)}\n")

    # ---- write paired CSV ----
    pair_fields = (["stratum", "ai_repo", "ctrl_repo"]
                   + [f"ai_{m}" for m in METRICS] + [f"ctrl_{m}" for m in METRICS]
                   + [f"delta_{m}" for m in METRICS])
    rows_out = []
    for p in usable_pairs:
        ai, ctrl = metrics[p["ai_repo"]], metrics[p["ctrl_repo"]]
        row = {"stratum": p["stratum"], "ai_repo": p["ai_repo"], "ctrl_repo": p["ctrl_repo"]}
        for m in METRICS:
            a, c = derived_value(ai, m), derived_value(ctrl, m)
            row[f"ai_{m}"], row[f"ctrl_{m}"] = fmt(a), fmt(c)
            row[f"delta_{m}"] = fmt(a - c) if a != "" and c != "" else ""
        rows_out.append(row)

    with open(args.out_pairs, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pair_fields)
        w.writeheader()
        w.writerows(rows_out)

    # ---- stats per metric ----
    lines.append("\nmetric | n | AI median | Ctrl median | Wilcoxon p | "
                 "paired-t p | rank-biserial r\n" + "-" * 88)
    for m in METRICS:
        deltas, ai_vals, ctrl_vals = [], [], []
        for row in rows_out:
            d = row[f"delta_{m}"]
            if d == "":
                continue
            a, c = float(row[f"ai_{m}"]), float(row[f"ctrl_{m}"])
            deltas.append(a - c)
            ai_vals.append(a)
            ctrl_vals.append(c)
        n = len(deltas)
        if n < 5:
            lines.append(f"{m}: n={n} — too few pairs")
            continue
        try:
            wil_p = stats.wilcoxon(deltas).pvalue
        except ValueError:
            wil_p = float("nan")  # all-zero deltas
        t_p = stats.ttest_rel(ai_vals, ctrl_vals).pvalue
        # matched-pairs rank-biserial: (sum positive ranks - sum negative)/total
        import numpy as np
        import statistics as st
        d = np.array(deltas)
        d_nz = d[d != 0]
        if len(d_nz):
            ranks = stats.rankdata(np.abs(d_nz))
            rp = ranks[d_nz > 0].sum()
            rn = ranks[d_nz < 0].sum()
            r_eff = f"{(rp - rn) / ranks.sum():+.3f}"
        else:
            r_eff = "0.000"
        lines.append(
            f"{m}: n={n} | AI={st.median(ai_vals):.4g} | "
            f"Ctrl={st.median(ctrl_vals):.4g} | Wil p={wil_p:.4f} | "
            f"t p={t_p:.4f} | r={r_eff}")

    summary = "\n".join(lines)
    open(args.out_summary, "w").write(summary + "\n")
    print(summary)
    print(f"\nwrote {args.out_pairs} and {args.out_summary}")


if __name__ == "__main__":
    main()
