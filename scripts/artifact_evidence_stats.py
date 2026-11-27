#!/usr/bin/env python3
"""Join the artefact scan to the arms and report what it does to the null.

Three numbers matter:

  1. How often a strong AI-tooling artefact appears in each evidence tier of the
     AI arm. If query-only repos carry artefacts at a similar rate to repos with
     an agent commit, then "85% unverifiable" is an artefact of using only the
     commit scan, and the arm is more verifiable than reported.
  2. How often a strong artefact appears in the control arm. Its whole design is
     "no AI mention, no bot commit", so a control repo with .cursorrules or a
     .claude/ directory is likely a contaminated control.
  3. What that contamination does to the measured effect. Misclassification runs
     one way here, so it dilutes: if a share c of controls is really AI-assisted,
     the observed difference is roughly (1 - 2c) of the true one.

Usage:
    .venv/bin/python scripts/artifact_evidence_stats.py \
        --artifacts data/ai_artifacts.csv --out data/artifact_evidence_stats.txt
"""
import argparse
import csv

STRONG = {"cursor_rules", "claude", "copilot", "windsurf", "aider",
          "cline_roo", "continue", "specstory", "mcp"}
WEAK = {"agents_md", "prompt_library"}


def load_artifacts(path):
    out = {}
    for r in csv.DictReader(open(path)):
        if r["status"] != "ok":
            continue
        kinds = set(k for k in (r.get("kinds") or "").split("|") if k)
        out[r["repo"]] = {"kinds": kinds, "strong": bool(kinds & STRONG),
                          "weak_only": bool(kinds & WEAK) and not (kinds & STRONG)}
    return out


def band(ev):
    ev = str(ev)
    if ev.startswith("bot-contributor"):
        return "bot commit"
    if ev == "readme-declaration":
        return "README declaration"
    return "query only"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="data/ai_artifacts.csv")
    ap.add_argument("--ai", default="data/candidates_v2.csv")
    ap.add_argument("--controls", default="data/controls.csv")
    ap.add_argument("--out", default="data/artifact_evidence_stats.txt")
    args = ap.parse_args()

    art = load_artifacts(args.artifacts)
    ai = [r for r in csv.DictReader(open(args.ai)) if r.get("v2_verdict") == "accept"]
    ctl = [r for r in csv.DictReader(open(args.controls)) if r.get("verdict") == "accept"]

    out = []
    A = out.append

    A("=== AI-tooling artefacts as a second evidence instrument ===")
    A("")
    A("Strong artefacts: .cursorrules/.cursor/, .claude/ or CLAUDE.md, Copilot instruction")
    A("files, .windsurfrules, aider config, .clinerules/.roo, .continue, .specstory, MCP")
    A("config. Weak: AGENTS.md or a prompts/ directory on its own, which plenty of")
    A("non-AI repositories carry, including this study's own.")
    A("")

    A("--- AI arm, by evidence tier ---")
    A("")
    hdr = f"{'tier':20s} {'n':>4s} {'scanned':>8s} {'strong':>8s} {'strong %':>9s} {'weak only':>10s}"
    A(hdr)
    A("-" * len(hdr))
    for tier in ("bot commit", "README declaration", "query only"):
        rows = [r for r in ai if band(r["evidence"]) == tier]
        scanned = [r for r in rows if r["full_name"] in art]
        strong = sum(1 for r in scanned if art[r["full_name"]]["strong"])
        weak = sum(1 for r in scanned if art[r["full_name"]]["weak_only"])
        A(f"{tier:20s} {len(rows):4d} {len(scanned):8d} {strong:8d} "
          f"{strong / max(len(scanned), 1):9.0%} {weak:10d}")
    A("")

    ai_scanned = [r for r in ai if r["full_name"] in art]
    strong_any = [r for r in ai_scanned if art[r["full_name"]]["strong"]]
    commit_or_readme = [r for r in ai_scanned if band(r["evidence"]) != "query only"]
    either = [r for r in ai_scanned
              if band(r["evidence"]) != "query only" or art[r["full_name"]]["strong"]]
    A("Verifiability of the AI arm, both instruments together:")
    A(f"  scanned                          {len(ai_scanned):4d}")
    A(f"  commit or README evidence        {len(commit_or_readme):4d} "
      f"({len(commit_or_readme) / max(len(ai_scanned), 1):.1%})")
    A(f"  strong artefact evidence         {len(strong_any):4d} "
      f"({len(strong_any) / max(len(ai_scanned), 1):.1%})")
    A(f"  either instrument                {len(either):4d} "
      f"({len(either) / max(len(ai_scanned), 1):.1%})")
    A(f"  no evidence of any kind          {len(ai_scanned) - len(either):4d} "
      f"({1 - len(either) / max(len(ai_scanned), 1):.1%})")
    A("")

    A("--- Control arm (collected as no AI mention, no bot commit) ---")
    A("")
    ctl_scanned = [r for r in ctl if r["full_name"] in art]
    ctl_strong = sum(1 for r in ctl_scanned if art[r["full_name"]]["strong"])
    ctl_weak = sum(1 for r in ctl_scanned if art[r["full_name"]]["weak_only"])
    A(f"scanned {len(ctl_scanned)} of {len(ctl)}")
    A(f"  strong artefact present: {ctl_strong} ({ctl_strong / max(len(ctl_scanned), 1):.1%})")
    A(f"  weak only:               {ctl_weak} ({ctl_weak / max(len(ctl_scanned), 1):.1%})")
    A("")
    A("A control repo carrying .cursorrules or a .claude/ directory is not a clean")
    A("control under the study's own definition. Those are the likely contamination.")
    A("")

    A("=== What contamination does to the measured effect ===")
    A("")
    c = ctl_strong / max(len(ctl_scanned), 1)
    A(f"Measured contamination of the control arm: c = {c:.1%}.")
    A("")
    A("Two-sided misclassification dilutes a real difference by about (1 - c - f),")
    A("where c is the share of controls that are really AI-assisted and f is the")
    A("share of the AI arm that is really hand-written. c is measured above. f is")
    A("not identifiable from this data, so the dilution is bounded rather than")
    A("estimated:")
    A("")
    for f in (0.0, 0.1, 0.2, 0.4):
        keep = 1 - c - f
        A(f"  f = {f:4.0%}: measured effect is about {keep:.0%} of the true one, "
          f"so the true effect is up to {1 / keep:.2f}x larger")
    A("")
    A("This is dilution: it moves a real difference toward zero and does nothing to a")
    A("truly null result. It also cannot create a difference that is not there, so it")
    A("explains how a medium effect could hide in this sample but does not license")
    A("the claim that one is hiding.")
    A("")
    A("=== What this does not measure ===")
    A("")
    A("- Authors who scrub traces will not appear in either instrument. The AI arm is")
    A("  therefore a lower bound on AI-assisted repositories at every tier.")
    A("- Absence of artefacts is not evidence of hand-written code: many agent users")
    A("  never commit rule files, and some keep them outside the repository.")
    A("- Artefacts can be committed for other reasons (shared team config, a fork of a")
    A("  template that ships .cursorrules). Every flag here is suggestive, not proof.")

    text = "\n".join(out) + "\n"
    with open(args.out, "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
