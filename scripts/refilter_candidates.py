#!/usr/bin/env python3
"""Re-filter existing candidates.csv with v2 rules (no new API search needed).

v2 additions (from spot-check 2026-08-23, docs/spotcheck-2026-08-23.md):
  1. Exclude repos whose PURPOSE is AI tooling (tools FOR vibe-coders vs
     artifacts OF vibe-coding) — description/name regex.
  2. Exclude courses/tutorials by name.
  3. Bot-contributor scan (claude[bot], cursor, codex, copilot, ...) —
     positive evidence for AI arm; recorded per repo.
  4. License field recorded; unlicensed flagged (license required at clone time).

Usage:
    GITHUB_TOKEN=... python3 refilter_candidates.py \
        --in data/candidates.csv --out data/candidates_v2.csv
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"

# Purpose-is-AI-tooling patterns: repo is a tool FOR vibe coding / AI-assisted dev,
# not an application BUILT via vibe coding.
TOOLING_RE = re.compile(
    r"(tool|tools|platform|kit|devkit|agent|boilerplate|template|generator|"
    r"launcher|plugin system|framework|sdk|library|cli for|extension|mcp|"
    r"skills?|workflow|governance|assistant|copilot for|helper)",
    re.IGNORECASE)
VIBE_CONTEXT_RE = re.compile(r"(vibe.?cod|ai.?cod|claude|cursor|copilot|llm)", re.IGNORECASE)
COURSE_RE = re.compile(
    r"(course|tutorial|bootcamp|exercise|homework|assignment|lesson|wsq|tgs-)",
    re.IGNORECASE)
BOT_RE = re.compile(
    r"(claude|cursor|codex|copilot|devin|gemini|deepseek|swe-agent|aider|cognition)"
    r"(\[bot\])?$|bot$", re.IGNORECASE)


def gh_json(path, token, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt == 5:
                raise
            time.sleep(2 ** attempt)


def classify(row, token):
    """Return (verdict, reason, extra_fields)."""
    name = row["full_name"].split("/")[-1]
    full = row["full_name"]

    # fetch description + license fresh from API (CSV lacks them)
    repo = gh_json(f"/repos/{full}", token)
    desc = repo.get("description") or ""
    lic = (repo.get("license") or {}).get("spdx_id") or "none"

    # 1. course/tutorial by name or description
    if COURSE_RE.search(name) or COURSE_RE.search(desc[:200]):
        return "reject", "course/tutorial", {"license": lic, "desc": desc[:200]}

    # 2. purpose-is-tooling: vibe/AI context word AND tooling word together in
    #    description or name → it's a tool FOR the workflow, not built BY it.
    ctx = VIBE_CONTEXT_RE.search(desc[:300]) or VIBE_CONTEXT_RE.search(name)
    tooling = TOOLING_RE.search(desc[:300]) or TOOLING_RE.search(name)
    # Heuristic: only reject when BOTH present and description is primarily
    # about the tooling itself (mentions 'for', 'help', 'manage' + dev words).
    DEV_PURPOSE_RE = re.compile(
        r"(for vibe|for ai|for developers|for llm|for claude|for cursor|"
        r"for copilot|coding assistant|code review|pair program)", re.IGNORECASE)
    if ctx and tooling and DEV_PURPOSE_RE.search(desc[:300]):
        return "reject", "ai-tooling-purpose", {"license": lic, "desc": desc[:200]}

    # 3. bot contributors scan
    bots = []
    try:
        contribs = gh_json(f"/repos/{full}/contributors?per_page=30", token)
        if isinstance(contribs, list):
            for c in contribs:
                login = c.get("login", "")
                if BOT_RE.match(login) and login.lower() not in ("dependabot",):
                    bots.append(login)
    except Exception:
        pass

    extra = {
        "license": lic,
        "desc": desc[:200],
        "bots": ";".join(bots),
        "evidence": "",
    }
    # evidence tiers: declared > bots > query-only
    readme_declared = row["reason"] == "declared-ai"
    if bots:
        extra["evidence"] = f"bot-contributor:{','.join(bots)}"
    elif readme_declared:
        extra["evidence"] = "readme-declaration"
    else:
        extra["evidence"] = "query-only"

    verdict = "accept"
    reason = extra["evidence"]
    if lic == "none":
        reason += "|unlicensed"  # accept but flag; enforced at clone time
    return verdict, reason, extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--infile", default="data/candidates.csv")
    ap.add_argument("--out", default="data/candidates_v2.csv")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")

    rows = [r for r in csv.DictReader(open(args.infile))
            if r["passed_filter"] == "True"]
    print(f"Re-filtering {len(rows)} previously-passed candidates")

    out_rows = []
    counts = {"accept": 0, "reject": 0}
    for i, row in enumerate(rows, 1):
        try:
            verdict, reason, extra = classify(row, token)
        except Exception as e:
            verdict, reason, extra = "reject", f"api-error:{e}", {}
        counts[verdict] += 1
        out = dict(row)
        out.update(extra)
        out["v2_verdict"] = verdict
        out["v2_reason"] = reason
        out_rows.append(out)
        print(f"[{i}/{len(rows)}] {verdict.upper():6s} {row['full_name']} ({reason})")
        time.sleep(0.8)

    fields = list({k for r in out_rows for k in r})
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted(fields))
        w.writeheader()
        w.writerows(out_rows)

    print(f"\nAccepted: {counts['accept']}  Rejected: {counts['reject']}")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
