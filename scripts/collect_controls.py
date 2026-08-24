#!/usr/bin/env python3
"""Collect the CONTROL arm: traditionally-written Python applications.

Inverted signals vs collect_candidates.py:
  - NO AI mentions in README (not even casual mentions — strict, per
    docs/control-group-criteria.md decision 2026-08-23)
  - NO bot contributors (claude/copilot/cursor/codex/...)
  - License required
  - Matched profile: created 2024-2026, low-star bands like the AI arm

Sourcing strategy: search for Python repos by generic app-ish terms and
recent creation dates, then filter out anything with AI contamination.
Queries deliberately avoid AI/vibe terms.

Usage:
    GITHUB_TOKEN=... python3 scripts/collect_controls.py --out data/controls.csv
"""
import argparse
import base64
import csv
import json
import os
import re
import sys
import time
import urllib.parse

from refilter_candidates import gh_json, BOT_RE  # reuse helpers

# Monthly slices keep each query well under GitHub's 1000-result cap.
QUERIES = [
    f"language:python created:{y}-{m:02d}-01..{y}-{m:02d}-28 stars:1..50"
    for y, m in [
        (2026, 8), (2026, 7), (2026, 6), (2026, 5), (2026, 4),
        (2026, 3), (2026, 2), (2026, 1),
        (2025, 12), (2025, 11), (2025, 10), (2025, 9), (2025, 8),
        (2025, 7), (2025, 6), (2025, 5), (2025, 4), (2025, 3),
        (2025, 2), (2025, 1),
        (2024, 12), (2024, 11), (2024, 10), (2024, 9), (2024, 8),
        (2024, 7), (2024, 6), (2024, 5), (2024, 4), (2024, 3),
        (2024, 2), (2024, 1),
    ]
]

AI_MENTION_RE = re.compile(
    r"\b(vibe.?cod|ai.?cod|built with|generated with|created using|developed using|"
    r"copilot|cursor|claude|chatgpt|gpt-?[345o]|gemini|deepseek|llm|aider|"
    r"openai|anthropic)\b", re.IGNORECASE)
COURSE_RE = re.compile(r"(course|tutorial|bootcamp|exercise|homework|assignment)", re.IGNORECASE)
LIBRARY_HINT_RE = re.compile(r"(library|sdk|framework|api client|wrapper|binding)", re.IGNORECASE)

TARGET = int(os.environ.get("CONTROL_TARGET", "80"))


def readme_text(full, token):
    try:
        data = gh_json(f"/repos/{full}/readme", token)
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def check_repo(repo, token):
    """Return (verdict, reason, extra). verdict in accept/reject."""
    full = repo["full_name"]
    name = full.split("/")[-1]
    lic = (repo.get("license") or {}).get("spdx_id") or "none"
    desc = repo.get("description") or ""

    if lic == "none":
        return "reject", "no-license", {}
    if COURSE_RE.search(name) or COURSE_RE.search(desc[:200]):
        return "reject", "course/tutorial", {"license": lic}
    if LIBRARY_HINT_RE.search(desc[:200]):
        return "reject", "library-not-app", {"license": lic}
    # structural checks mirror v1
    if not (50 <= repo["size"] <= 50000):
        return "reject", "size-out-of-band", {"license": lic}

    tree = gh_json(f"/repos/{full}/git/trees/{repo['default_branch']}?recursive=1", token)
    paths = [t["path"] for t in tree.get("tree", []) if t["type"] == "blob"]
    py = [p for p in paths if p.endswith(".py") and ".venv" not in p and "site-packages" not in p]
    if len(py) < 5:
        return "reject", f"only {len(py)} py files", {"license": lic}

    rd = readme_text(full, token)
    if AI_MENTION_RE.search(rd[:5000]):
        return "reject", "ai-mention-in-readme", {"license": lic}

    # bot contributors = instant disqualify (contamination)
    try:
        contribs = gh_json(f"/repos/{full}/contributors?per_page=30", token)
        if isinstance(contribs, list):
            logins = [c.get("login", "") for c in contribs]
            bots = [l for l in logins if BOT_RE.match(l)]
            if bots:
                return "reject", f"bot-contributor:{','.join(bots)}", {"license": lic}
    except Exception:
        pass

    return "accept", "clean-control", {
        "license": lic,
        "desc": desc[:200],
        "py_files": len(py),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/controls.csv")
    ap.add_argument("--years", default="",
                    help="comma-separated years to restrict monthly slices to, e.g. --years 2024,2025")
    args = ap.parse_args()
    if args.years:
        years = {y.strip() for y in args.years.split(",")}
        global QUERIES
        QUERIES = [q for q in QUERIES if any(f"created:{y}-" in q for y in years)]
        print(f"Restricted to year(s) {sorted(years)}: {len(QUERIES)} slices")
    token = os.environ.get("GITHUB_TOKEN")

    fields = ["full_name","stars","size_kb","created","pushed","url",
              "verdict","reason","arm","license","desc","py_files"]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    def load_existing():
        if os.path.exists(args.out):
            return list(csv.DictReader(open(args.out)))
        return []

    def save(accepts_new):
        old = load_existing()
        merged = {(r["full_name"], r["verdict"]): r for r in old}
        for r in accepts_new:
            merged[(r["full_name"], r["verdict"])] = r
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(merged.values())
        n = sum(1 for r in merged.values() if r["verdict"] == "accept")
        return len(merged), n

    accepted, seen = [], []
    for qi, q in enumerate(QUERIES):
        if len(accepted) >= TARGET:
            break
        print(f"== query [{qi+1}/{len(QUERIES)}]: {q}")
        for page in range(1, 11):  # GitHub caps search at 1000 results (10 pages)
            if len(accepted) >= TARGET:
                break
            try:
                data = gh_json("/search/repositories", token, {
                    "q": q, "per_page": 100, "page": page,
                    "sort": "updated", "order": "desc"})
            except Exception as e:
                print(f"  query failed ({e}); moving on", file=sys.stderr)
                break
            items = data.get("items", [])
            if not items:
                break
            for repo in items:
                full = repo["full_name"]
                if full in seen or repo.get("fork"):
                    continue
                seen.append(full)
                verdict, reason, extra = check_repo(repo, token)
                row = {
                    "full_name": full, "stars": repo["stargazers_count"],
                    "size_kb": repo["size"], "created": repo["created_at"][:10],
                    "pushed": repo["pushed_at"][:10], "url": repo["html_url"],
                    "verdict": verdict, "reason": reason,
                    "arm": "control", **extra,
                }
                print(f"{verdict.upper():6s} {full} ({reason})")
                if verdict == "accept":
                    accepted.append(row)
                    _, total = save(accepted)  # incremental: survive crashes
                    print(f"  -> {total} controls on file")
                    if len(accepted) >= TARGET:
                        break
                time.sleep(0.8)
            time.sleep(7)

    total_rows, n_accept = save(accepted)
    print(f"\nAccepted this run: {len(accepted)} | total controls on file: {n_accept}")


if __name__ == "__main__":
    main()
