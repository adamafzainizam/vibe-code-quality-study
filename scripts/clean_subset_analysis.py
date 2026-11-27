"""Clean-subset re-analysis: does the direction survive when both arms are clean?

The 46 pairs contain an unknown share of misclassified repos in both directions:
AI-arm repos with no trace of an agent, control repos that ship AI tooling. If
contamination is diluting a real difference, the pairs where both sides are
unambiguous should show a larger effect than the pairs that are not.

"Clean" here means: the AI side has an agent commit, a README declaration or a
strong tooling artefact, AND the control side has neither a strong nor weak AI
artefact and no bot commit (controls were already screened for the last one).

This is a post hoc subset, so it is exploratory. It exists to decide whether a
full rebuild is worth the collection cost, not to report a result.
"""
import csv

import numpy as np
from scipy import stats

STRONG = {"cursor_rules", "claude", "copilot", "windsurf", "aider",
          "cline_roo", "continue", "specstory", "mcp"}
WEAK = {"agents_md", "prompt_library"}
METRICS = ["pct_cc_gt_10", "lizard_avg_ccn", "lizard_avg_nloc",
           "comment_ratio", "docstring_viols_per_kloc", "sloc"]


def kinds(path):
    out = {}
    for r in csv.DictReader(open(path)):
        if r["status"] != "ok":
            continue
        out[r["repo"]] = set(k for k in (r.get("kinds") or "").split("|") if k)
    return out


def main():
    art = kinds("data/ai_artifacts.csv")
    pairs = list(csv.DictReader(open("data/matched_pairs_v2.csv")))
    ps = {r["ai_repo"]: r for r in csv.DictReader(open("data/paired_stats.csv"))}

    def ai_clean(p):
        ev = str(p["ai_evidence"])
        k = art.get(p["ai_repo"], set())
        return ev.startswith("bot-contributor") or ev == "readme-declaration" or bool(k & STRONG)

    def ctrl_clean(p):
        return not (art.get(p["ctrl_repo"], set()) & (STRONG | WEAK))

    clean = [p for p in pairs if ai_clean(p) and ctrl_clean(p) and p["ai_repo"] in ps]
    dirty = [p for p in pairs if p["ai_repo"] in ps and p not in clean]

    print(f"pairs total {len(pairs)}, both sides clean {len(clean)}, "
          f"not clean {len(dirty)}")
    print()
    hdr = f"{'metric':28s} {'clean n':>7s} {'clean d_z':>10s} {'dirty n':>7s} {'dirty d_z':>10s} {'clean p':>8s}"
    print(hdr)
    print("-" * len(hdr))
    for m in METRICS:
        c = np.array([float(ps[p["ai_repo"]][f"delta_{m}"]) for p in clean])
        d = np.array([float(ps[p["ai_repo"]][f"delta_{m}"]) for p in dirty])
        cz = c.mean() / c.std(ddof=1) if len(c) > 2 and c.std(ddof=1) else float("nan")
        dz = d.mean() / d.std(ddof=1) if len(d) > 2 and d.std(ddof=1) else float("nan")
        p = stats.wilcoxon(c).pvalue if len(c) >= 8 and not np.allclose(c, 0) else float("nan")
        print(f"{m:28s} {len(c):7d} {cz:10.3f} {len(d):7d} {dz:10.3f} {p:8.3f}")

    print()
    print("clean pairs (AI evidence, control with no AI artefacts at all):")
    for p in clean:
        print(f"  {p['ai_repo']:45s} vs {p['ctrl_repo']:45s} [{p['ai_evidence']}]")


if __name__ == "__main__":
    main()
