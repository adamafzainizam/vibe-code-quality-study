#!/usr/bin/env python3
"""Measure the licence base rate in the traditional arm, WITHOUT a licence gate.

Why this exists
---------------
The control arm was collected with "license required" (collect_controls.py), and
the AI arm was not: refilter_candidates.py accepted unlicensed repositories and
flagged them, leaving the licence check to clone time in analyze_repos.py. The
result is that every licence-gated repo in the study was an AI-arm repo, so the
40-vs-0 attrition says nothing about base rates.

This script re-runs the control arm's search with its structural filters intact
and the licence requirement REMOVED, recording the licence instead of rejecting
on it. That turns "how many AI repos have no licence" into a comparison against
the population it was drawn from.

Filters kept identical to collect_controls.check_repo:
  - course/tutorial by name or description
  - library-not-app by description
  - size 50..50000 KB
  - at least 5 .py files in the default branch
  - no AI mention in the first 5000 chars of the README (strict)
  - no bot contributors (contamination)

Filters changed: none. Only the licence rejection is removed, and the reason
string records what the licence was.

Output columns match collect_controls.csv plus `recognised`, so the two can be
compared row for row.

Usage:
    export GITHUB_TOKEN=$(gh auth token)
    LICENCE_TARGET=200 .venv/bin/python scripts/collect_license_base_rate.py \
        --out data/license_base_rate.csv
"""
import argparse
import base64
import csv
import os
import sys
import time

from refilter_candidates import gh_json, BOT_RE
from collect_controls import QUERIES, AI_MENTION_RE, COURSE_RE, LIBRARY_HINT_RE, readme_text
from analyze_repos import RECOGNIZED_LICENSES

TARGET = int(os.environ.get("LICENCE_TARGET", "200"))

FIELDS = ["full_name", "stars", "size_kb", "created", "pushed", "url",
          "license", "recognised", "verdict", "reason", "arm", "desc", "py_files"]


def check_repo(repo, token):
    """Return (verdict, reason, extra). Licence is recorded, never a rejection."""
    full = repo["full_name"]
    name = full.split("/")[-1]
    lic = ((repo.get("license") or {}).get("spdx_id") or "none")
    lic = lic.lower()
    desc = repo.get("description") or ""
    extra = {"license": lic, "recognised": str(lic in RECOGNIZED_LICENSES)}

    if COURSE_RE.search(name) or COURSE_RE.search(desc[:200]):
        return "reject", "course/tutorial", extra
    if LIBRARY_HINT_RE.search(desc[:200]):
        return "reject", "library-not-app", extra
    if not (50 <= repo["size"] <= 50000):
        return "reject", "size-out-of-band", extra

    try:
        tree = gh_json(f"/repos/{full}/git/trees/{repo['default_branch']}?recursive=1", token)
    except Exception as e:
        return "error", f"tree:{str(e)[:40]}", extra
    paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
    py = [p for p in paths if p.endswith(".py") and ".venv" not in p and "site-packages" not in p]
    if len(py) < 5:
        return "reject", f"only {len(py)} py files", extra
    extra["py_files"] = len(py)

    rd = readme_text(full, token)
    if AI_MENTION_RE.search(rd[:5000]):
        return "reject", "ai-mention-in-readme", extra

    try:
        contribs = gh_json(f"/repos/{full}/contributors?per_page=30", token)
        if isinstance(contribs, list):
            bots = [c.get("login", "") for c in contribs if BOT_RE.match(c.get("login", ""))]
            if bots:
                return "reject", f"bot-contributor:{','.join(bots)}", extra
    except Exception:
        pass

    return "accept", "clean-control", extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/license_base_rate.csv")
    ap.add_argument("--years", default="2024,2025,2026")
    ap.add_argument("--max-examined", type=int, default=4000,
                    help="guard against a runaway run when the accept rate is low")
    args = ap.parse_args()

    years = {y.strip() for y in args.years.split(",") if y.strip()}
    queries = [q for q in QUERIES if any(f"created:{y}-" in q for y in years)]
    print(f"{len(queries)} monthly slices, target {TARGET} accepted", flush=True)

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN not set (use: export GITHUB_TOKEN=$(gh auth token))")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    rows = []
    if os.path.exists(args.out):
        rows = list(csv.DictReader(open(args.out)))
        print(f"resuming with {len(rows)} rows already on file", flush=True)

    def save():
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    seen = {r["full_name"] for r in rows}
    accepted = sum(1 for r in rows if r["verdict"] == "accept")
    examined = 0

    for qi, q in enumerate(queries):
        if accepted >= TARGET or examined >= args.max_examined:
            break
        print(f"== slice [{qi+1}/{len(queries)}]: {q} (accepted {accepted})", flush=True)
        for page in range(1, 6):
            if accepted >= TARGET or examined >= args.max_examined:
                break
            try:
                data = gh_json("/search/repositories", token, {
                    "q": q, "per_page": 100, "page": page,
                    "sort": "updated", "order": "desc"})
            except Exception as e:
                print(f"  search failed ({e}); next slice", file=sys.stderr, flush=True)
                break
            items = data.get("items", [])
            if not items:
                break
            for repo in items:
                if accepted >= TARGET or examined >= args.max_examined:
                    break
                full = repo["full_name"]
                if full in seen or repo.get("fork"):
                    continue
                seen.add(full)
                examined += 1
                verdict, reason, extra = check_repo(repo, token)
                row = {
                    "full_name": full, "stars": repo["stargazers_count"],
                    "size_kb": repo["size"], "created": repo["created_at"][:10],
                    "pushed": repo["pushed_at"][:10], "url": repo["html_url"],
                    "verdict": verdict, "reason": reason, "arm": "control-nogate",
                    **extra,
                }
                rows.append(row)
                if verdict == "accept":
                    accepted += 1
                    save()
                    print(f"ACCEPT {full} ({extra['license']}) -> {accepted}", flush=True)
                time.sleep(0.6)
            time.sleep(6)

    save()
    print(f"\nexamined {examined}, accepted {accepted}, rows on file {len(rows)}", flush=True)


if __name__ == "__main__":
    main()
