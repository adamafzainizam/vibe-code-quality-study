#!/usr/bin/env python3
"""Second evidence instrument: AI-tooling artefacts committed to the tree.

A bot co-authored commit is only one trace an agent leaves. Agents also leave
files: rule sets, prompt libraries, MCP configs, agent instruction files. Those
survive even when the author rewrites commits or squashes history, so their
presence measures something the commit scan cannot see.

The opposite also happens, which is why this script exists: people strip the
traces on purpose. That cuts two ways and both are recorded here:

  - a repository with tooling artefacts but no bot commit is probably still
    AI-assisted (the commit scan under-counts)
  - a repository in the control arm with tooling artefacts is probably
    contaminated, which attenuates any real difference the study measures

Arm-blind, like the other measurement scripts: it takes names, writes presence
flags, and never reads which arm a repository belongs to.

Usage:
    .venv/bin/python scripts/detect_ai_artifacts.py \
        --ai data/candidates_v2.csv --controls data/controls.csv \
        --out data/ai_artifacts.csv
"""
import argparse
import concurrent.futures as cf
import csv
import json
import os
import re
import subprocess

# Committed artefacts that indicate an agent-driven workflow. Matching is on the
# path, case-insensitively, so .cursorrules / .CursorRules both count.
PATTERNS = {
    "cursor_rules": r"(^|/)\.cursorrules$|(^|/)\.cursor(/|$)|(^|/)\.cursorignore$",
    "claude": r"(^|/)CLAUDE\.md$|(^|/)\.claude(/|$)",
    "copilot": r"(^|/)\.github/copilot-instructions\.md$|(^|/)\.github/instructions(/|$)",
    "windsurf": r"(^|/)\.windsurf(rules)?(/|$)",
    "aider": r"(^|/)\.aider(\.conf\.yml|\.ignore|rc)?$|(^|/)CONVENTIONS\.md$",
    "agents_md": r"(^|/)AGENTS\.md$",
    "cline_roo": r"(^|/)\.clinerules(/|$)|(^|/)\.roo(/|$)|(^|/)\.kilocode(/|$)",
    "continue": r"(^|/)\.continue(/|$)|(^|/)\.continuedev(/|$)",
    "specstory": r"(^|/)\.specstory(/|$)",
    "mcp": r"(^|/)(\.mcp\.json|mcp\.json|mcp-config\.json)$",
    "prompt_library": r"(^|/)(prompts?|\.prompts)(/|$)|(^|/)PROMPT\.md$",
}
COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in PATTERNS.items()}
FIELDS = ["repo", "status", "n_files", "truncated", "any_artifact",
          "n_artifact_kinds", "kinds"]


def gh_json(args):
    out = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def check(full):
    repo = gh_json(["api", f"repos/{full}", "--jq", "{d:.default_branch}"])
    if not repo:
        return {"repo": full, "status": "api-failed"}
    branch = repo["d"]
    tree = gh_json(["api", f"repos/{full}/git/trees/{branch}?recursive=1"])
    if not tree or "tree" not in tree:
        return {"repo": full, "status": "tree-failed"}
    paths = [t["path"] for t in tree["tree"] if t.get("type") == "blob"]
    kinds = sorted({k for k, rx in COMPILED.items() for p in paths if rx.search(p)})
    return {"repo": full, "status": "ok", "n_files": len(paths),
            "truncated": int(bool(tree.get("truncated"))),
            "any_artifact": int(bool(kinds)), "n_artifact_kinds": len(kinds),
            "kinds": "|".join(kinds)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai", default="data/candidates_v2.csv")
    ap.add_argument("--controls", default="data/controls.csv")
    ap.add_argument("--out", default="data/ai_artifacts.csv")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    names = set()
    for r in csv.DictReader(open(args.ai)):
        if r.get("v2_verdict") == "accept":
            names.add(r["full_name"])
    for r in csv.DictReader(open(args.controls)):
        if r.get("verdict") == "accept":
            names.add(r["full_name"])
    names = sorted(names)
    print(f"{len(names)} repos to scan", flush=True)

    done = {}
    if os.path.exists(args.out):
        for r in csv.DictReader(open(args.out)):
            done[r["repo"]] = r
        print(f"resuming with {len(done)} scanned", flush=True)

    todo = [n for n in names if done.get(n, {}).get("status") != "ok"]

    def save():
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(done.values())

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, rec in enumerate(ex.map(check, todo), 1):
            done[rec["repo"]] = rec
            if i % 25 == 0:
                save()
                print(f"  {i}/{len(todo)}", flush=True)
    save()
    ok = sum(1 for r in done.values() if r["status"] == "ok")
    # values are ints in a fresh run and strings when resumed from CSV
    hit = sum(1 for r in done.values() if str(r.get("any_artifact")) == "1")
    print(f"scanned {ok}/{len(names)} ok, {hit} with artefacts", flush=True)


if __name__ == "__main__":
    main()
