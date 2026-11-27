#!/usr/bin/env python3
"""Licence presence: AI-assisted arm vs traditionally-written arm, no gate.

The study gated licences only on the traditional arm at collection time
(collect_controls.py rejected "no-license"), so the licence attrition in the
analysis was one-sided by construction. data/license_base_rate.csv re-collects
a traditional arm with the same structural filters and no licence gate, which
makes the comparison meaningful.

Reports:
  1. Unlicensed share in each arm, Fisher exact test, odds ratio with 95% CI.
  2. The same stratified by star band and size band, with a Mantel-Haenszel
     pooled odds ratio, because licence presence rises with repo age/size and
     the arms could differ on those.
  3. Permissive vs copyleft mix among licensed repos, as a secondary question.

Usage:
    .venv/bin/python scripts/license_base_rate_analysis.py \
        --ai data/candidates_v2.csv \
        --controls data/license_base_rate.csv \
        --out data/license_base_rate_stats.txt
"""
import argparse
import collections
import csv
import math

from scipy import stats

PERMISSIVE = {"mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause", "isc", "unlicense"}
COPYLEFT = {"gpl-3.0", "gpl-2.0", "agpl-3.0", "lgpl-3.0", "mpl-2.0"}


def norm_lic(v):
    v = (v or "").strip().lower()
    return "none" if v in ("", "none", "nan") else v


def load_ai(path):
    rows = [r for r in csv.DictReader(open(path)) if r.get("v2_verdict") == "accept"]
    return [{"full_name": r["full_name"], "lic": norm_lic(r.get("license")),
             "stars": int(float(r["stars"] or 0)), "size_kb": int(float(r["size_kb"] or 0)),
             "year": (r.get("created") or "")[:4]} for r in rows]


def load_controls(path):
    rows = [r for r in csv.DictReader(open(path)) if r["verdict"] == "accept"]
    return [{"full_name": r["full_name"], "lic": norm_lic(r.get("license")),
             "stars": int(float(r["stars"] or 0)), "size_kb": int(float(r["size_kb"] or 0)),
             "year": (r.get("created") or "")[:4]} for r in rows]


def two_by_two(a_pos, a_n, b_pos, b_n):
    """Fisher exact + Woolf OR with 95% CI. pos = unlicensed."""
    table = [[a_pos, a_n - a_pos], [b_pos, b_n - b_pos]]
    orr, p = stats.fisher_exact(table)
    # Woolf CI with a Haldane-style correction when a cell is empty
    A, B = a_pos + 0.5, a_n - a_pos + 0.5
    C, D = b_pos + 0.5, b_n - b_pos + 0.5
    lor = math.log((A * D) / (B * C))
    se = math.sqrt(1 / A + 1 / B + 1 / C + 1 / D)
    ci = (math.exp(lor - 1.96 * se), math.exp(lor + 1.96 * se))
    return orr, p, ci


def star_band(s):
    return "1-10" if s <= 10 else ("11-50" if s <= 50 else ">50")


def size_band(kb):
    return "50-300" if kb <= 300 else ("300-3k" if kb <= 3000 else ">3k")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai", default="data/candidates_v2.csv")
    ap.add_argument("--controls", default="data/license_base_rate.csv")
    ap.add_argument("--gated", default="data/controls.csv")
    ap.add_argument("--out", default="data/license_base_rate_stats.txt")
    args = ap.parse_args()

    ai = load_ai(args.ai)
    ctl = load_controls(args.controls)
    out = []
    A = out.append

    def share(rows):
        n = len(rows)
        none = sum(1 for r in rows if r["lic"] == "none")
        noassert = sum(1 for r in rows if r["lic"] in ("noassertion", "other"))
        recog = n - none - noassert
        return n, none, noassert, recog

    an, a_none, a_na, a_rec = share(ai)
    cn, c_none, c_na, c_rec = share(ctl)

    A("=== Licence presence, AI-assisted vs traditional (no licence gate) ===")
    A("")
    A(f"AI-assisted candidates (vibe queries, v2 accept):      n={an}")
    A(f"  no licence                                         {a_none:4d} ({a_none / an:.1%})")
    A(f"  licence file GitHub cannot identify (NOASSERTION)  {a_na:4d} ({a_na / an:.1%})")
    A(f"  recognised OSS licence                             {a_rec:4d} ({a_rec / an:.1%})")
    A("")
    A(f"Traditional candidates (same filters, no gate):        n={cn}")
    A(f"  no licence                                         {c_none:4d} ({c_none / cn:.1%})")
    A(f"  licence file GitHub cannot identify (NOASSERTION)  {c_na:4d} ({c_na / cn:.1%})")
    A(f"  recognised OSS licence                             {c_rec:4d} ({c_rec / cn:.1%})")
    A("")

    # The study's own control arm, gated on licence at collection time
    if args.gated:
        try:
            gated = load_controls(args.gated)
            gn, g_none, _, g_rec = share(gated)
            A(f"For reference, the study's licence-gated control arm (data/controls.csv):")
            A(f"  n={gn}, no licence {g_none} ({g_none / gn:.1%}), recognised {g_rec} ({g_rec / gn:.1%})")
            A("  -> that arm cannot have an unlicensed row, so it cannot estimate a base rate.")
            A("")
        except FileNotFoundError:
            pass

    orr, p, ci = two_by_two(a_none, an, c_none, cn)
    A("Unlicensed vs licensed, AI arm against traditional arm:")
    A(f"  odds ratio {orr:.2f} (95% CI {ci[0]:.2f} to {ci[1]:.2f}), Fisher exact p={p:.3g}")
    higher = "AI-assisted" if a_none / an > c_none / cn else "traditional"
    A(f"  {higher} repositories are the ones more often unlicensed.")
    A("")

    A("=== Stratified by star band (unlicensed share) ===")
    A("")
    A(f"{'band':8s} {'AI n':>5s} {'AI unlic':>9s} {'trad n':>7s} {'trad unlic':>11s} {'OR':>7s} {'p':>8s}")
    strata = []
    for band in ("1-10", "11-50", ">50"):
        ar = [r for r in ai if star_band(r["stars"]) == band]
        cr = [r for r in ctl if star_band(r["stars"]) == band]
        if len(ar) < 5 or len(cr) < 5:
            A(f"{band:8s} {len(ar):5d} {'(too few)':>9s} {len(cr):7d} {'':>11s}")
            continue
        a1 = sum(1 for r in ar if r["lic"] == "none")
        c1 = sum(1 for r in cr if r["lic"] == "none")
        o, pp, _ = two_by_two(a1, len(ar), c1, len(cr))
        A(f"{band:8s} {len(ar):5d} {a1:5d} ({a1 / len(ar):.0%}) {len(cr):7d} "
          f"{c1:5d} ({c1 / len(cr):.0%}) {o:7.2f} {pp:8.3g}")
        strata.append((a1, len(ar) - a1, c1, len(cr) - c1))
    if strata:
        num = sum((a1 * c0) / (a1 + a0 + c1 + c0) for a1, a0, c1, c0 in strata)
        den = sum((a0 * c1) / (a1 + a0 + c1 + c0) for a1, a0, c1, c0 in strata)
        A(f"\n  Mantel-Haenszel pooled OR across star bands: {num / den:.2f}"
          if den else "\n  Mantel-Haenszel undefined (empty stratum)")
    A("")

    A("=== Stratified by size band (unlicensed share) ===")
    A("")
    A(f"{'band':8s} {'AI n':>5s} {'AI unlic':>9s} {'trad n':>7s} {'trad unlic':>11s} {'OR':>7s} {'p':>8s}")
    for band in ("50-300", "300-3k", ">3k"):
        ar = [r for r in ai if size_band(r["size_kb"]) == band]
        cr = [r for r in ctl if size_band(r["size_kb"]) == band]
        if len(ar) < 5 or len(cr) < 5:
            A(f"{band:8s} {len(ar):5d} {'(too few)':>9s} {len(cr):7d} {'':>11s}")
            continue
        ap_ = sum(1 for r in ar if r["lic"] == "none")
        cp_ = sum(1 for r in cr if r["lic"] == "none")
        o, pp, _ = two_by_two(ap_, len(ar), cp_, len(cr))
        A(f"{band:8s} {len(ar):5d} {ap_:5d} ({ap_ / len(ar):.0%}) {len(cr):7d} "
          f"{cp_:5d} ({cp_ / len(cr):.0%}) {o:7.2f} {pp:8.3g}")
    A("")

    A("=== Licence family among licensed repos ===")
    A("")
    for name, rows in (("AI-assisted", ai), ("traditional", ctl)):
        lic = [r["lic"] for r in rows if r["lic"] not in ("none", "noassertion", "other")]
        perm = sum(1 for l in lic if l in PERMISSIVE)
        cop = sum(1 for l in lic if l in COPYLEFT)
        unknown = len(lic) - perm - cop
        A(f"  {name:12s} n={len(lic):4d}  permissive {perm:4d} ({perm / max(len(lic), 1):.0%})  "
          f"copyleft {cop:3d} ({cop / max(len(lic), 1):.0%})  other {unknown}")
    A("")
    a_lic = [r["lic"] for r in ai if r["lic"] not in ("none", "noassertion", "other")]
    c_lic = [r["lic"] for r in ctl if r["lic"] not in ("none", "noassertion", "other")]
    if a_lic and c_lic:
        tab = [[sum(1 for l in a_lic if l in COPYLEFT), sum(1 for l in a_lic if l not in COPYLEFT)],
               [sum(1 for l in c_lic if l in COPYLEFT), sum(1 for l in c_lic if l not in COPYLEFT)]]
        o, pp = stats.fisher_exact(tab)
        A(f"  copyleft share, AI vs traditional: OR {o:.2f}, Fisher p={pp:.3g}")
    A("")
    A("=== How to read this ===")
    A("")
    A("- Both arms come from GitHub search with the same structural filters (>=5 .py")
    A("  files, 50-50000 KB, app not library/course, 2024-2026, 1-50 stars). The AI")
    A("  arm is defined by self-declaration (vibe queries plus README/bot evidence);")
    A("  the traditional arm by the absence of any AI mention and of bot commits.")
    A("- The traditional arm comes from generic Python queries, not from a census of")
    A("  all Python repos, so the base rate is a sample estimate, not a population")
    A("  parameter. Different queries, same coarse profile.")
    A("- Licences are as GitHub reports them. NOASSERTION means a licence file that")
    A("  GitHub cannot map to an SPDX id, counted separately rather than as unlicensed.")

    text = "\n".join(out) + "\n"
    with open(args.out, "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
