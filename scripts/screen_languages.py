#!/usr/bin/env python3
"""Feasibility screen: how many VERIFIABLE candidates exist per language?

Python's rebuild is capped at 73 verifiable candidates, which is why the next step
is other languages. Before paying for clones, radon/lizard runs and matching, this
asks one question per language: how many repos can be both selected (structural
filters) and evidenced (agent commit, README declaration or committed tooling
artefact)?

Everything here is API only, no clones:
  search  -> one page set per query family
  tree    -> source-file count and AI-tooling artefacts in one call
  contributors -> agent commits
  readme  -> declaration, only for repos that pass the other filters

Output: data/lang_screen.csv, one row per candidate examined, plus a summary.

Usage:
    export GITHUB_TOKEN=$(gh auth token)
    .venv/bin/python scripts/screen_languages.py \
        --languages typescript,javascript,rust,java --per-lang 120
"""
import argparse
import base64
import concurrent.futures as cf
import csv
import json
import os
import re
import subprocess
import sys
import threading
import time

SRC_EXT = {
    "python": (".py",),
    "typescript": (".ts", ".tsx"),
    "javascript": (".js", ".jsx", ".mjs", ".cjs"),
    "rust": (".rs",),
    "java": (".java",),
}

QUERY_FAMILIES = [
    "topic:vibe-coding language:{L} stars:1..50",
    '"vibe coded" in:readme language:{L} stars:1..50',
    '"vibe-coding" in:readme language:{L} stars:1..50',
    '"built with cursor" in:readme language:{L} stars:1..50',
    '"generated with claude" in:readme language:{L} stars:1..50',
    "topic:ai-generated language:{L} stars:1..50",
]

ARTIFACTS = {
    "cursor": r"(^|/)\.cursorrules$|(^|/)\.cursor(/|$)|(^|/)\.cursorignore$",
    "claude": r"(^|/)CLAUDE\.md$|(^|/)\.claude(/|$)",
    "copilot": r"(^|/)\.github/copilot-instructions\.md$",
    "windsurf": r"(^|/)\.windsurf(rules)?(/|$)",
    "aider": r"(^|/)\.aider(\.conf\.yml|\.ignore|rc)?$",
    "cline_roo": r"(^|/)\.clinerules(/|$)|(^|/)\.roo(/|$)|(^|/)\.kilocode(/|$)",
    "continue": r"(^|/)\.continue(/|$)|(^|/)\.continuedev(/|$)",
    "specstory": r"(^|/)\.specstory(/|$)",
    "mcp": r"(^|/)\.mcp\.json$|(^|/)mcp-config\.json$",
}
ART_RE = {k: re.compile(v, re.IGNORECASE) for k, v in ARTIFACTS.items()}
STRONG = set(ARTIFACTS)
BOT_RE = re.compile(
    r"(claude|cursor|codex|copilot|devin|gemini|deepseek|swe-agent|aider|cognition)"
    r"(\[bot\])?$|bot$", re.IGNORECASE)
AI_MENTION_RE = re.compile(
    r"\b(vibe.?cod|ai.?cod|built with|generated with|copilot|cursor|claude|chatgpt|"
    r"gpt-?[345o]|gemini|deepseek|llm|aider|openai|anthropic)\b", re.IGNORECASE)
EXCLUDE_DIR = re.compile(r"(^|/)(\.venv|venv|node_modules|site-packages|target|dist|build|\.git)(/|$)")

FIELDS = ["language", "repo", "stars", "size_kb", "created", "license", "n_src",
          "artifacts", "bot", "readme_declared", "verifiable", "independent", "tier", "query"]
_lock = threading.Lock()


def gh(args, retries=3):
    for i in range(retries):
        out = subprocess.run(["gh"] + args, capture_output=True, text=True)
        if out.returncode == 0:
            try:
                return json.loads(out.stdout)
            except json.JSONDecodeError:
                return None
        if "rate limit" in out.stderr.lower() or "secondary" in out.stderr.lower():
            time.sleep(5 * (i + 1))
            continue
        return None
    return None


def readme_declares(full):
    data = gh(["api", f"repos/{full}/readme"])
    if not data or "content" not in data:
        return 0
    try:
        text = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return 0
    return int(bool(AI_MENTION_RE.search(text[:5000])))


def screen(repo, lang, query=""):
    full = repo["full_name"]
    row = {"language": lang, "repo": full, "stars": repo["stargazers_count"],
           "size_kb": repo["size"], "created": repo["created_at"][:10],
           "license": ((repo.get("license") or {}).get("spdx_id") or "none").lower()}
    if not (50 <= repo["size"] <= 50000):
        return {**row, "n_src": -1, "tier": "size-out"}
    tree = gh(["api", f"repos/{full}/git/trees/{repo['default_branch']}?recursive=1"])
    if not tree or "tree" not in tree:
        return {**row, "n_src": -1, "tier": "tree-failed"}
    paths = [t["path"] for t in tree["tree"] if t.get("type") == "blob"]
    paths = [p for p in paths if not EXCLUDE_DIR.search(p)]
    src = [p for p in paths if p.endswith(SRC_EXT[lang])]
    kinds = sorted({k for k, rx in ART_RE.items() for p in paths if rx.search(p)})
    row.update(n_src=len(src), artifacts="|".join(kinds))
    if len(src) < 5:
        return {**row, "tier": "too-few-src"}
    contribs = gh(["api", f"repos/{full}/contributors?per_page=30"])
    bots = []
    if isinstance(contribs, list):
        bots = sorted({c.get("login", "") for c in contribs
                       if BOT_RE.match(c.get("login", ""))})
    row["bot"] = "|".join(bots)
    row["readme_declared"] = readme_declares(full)
    row["query"] = query
    # "independent" = evidence not implied by the query that found the repo.
    # Three of the six families are README-text searches, so a README mention in
    # those is a declaration but not independent corroboration.
    tier = ("bot" if bots else
            "artifact" if kinds else
            "readme" if row["readme_declared"] else "query-only")
    row["verifiable"] = int(tier != "query-only")
    row["independent"] = int(tier in ("bot", "artifact"))
    row["tier"] = tier
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--languages", default="typescript,javascript,rust,java")
    ap.add_argument("--per-lang", type=int, default=120,
                    help="stop after this many screened candidates per language")
    ap.add_argument("--out", default="data/lang_screen.csv")
    args = ap.parse_args()
    if not os.environ.get("GITHUB_TOKEN") and not subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True).stdout.strip():
        sys.exit("no GitHub credentials available")

    rows = []
    for lang in [x.strip() for x in args.languages.split(",") if x.strip()]:
        seen, accepted = set(), 0
        print(f"\n== {lang}: up to {args.per_lang} screened candidates", flush=True)
        for fam in QUERY_FAMILIES:
            if accepted >= args.per_lang:
                break
            q = fam.format(L=lang)
            for page in (1, 2):
                if accepted >= args.per_lang:
                    break
                data = gh(["api", "-X", "GET", "search/repositories",
                           "-f", f"q={q}", "-f", "per_page=100", "-f", f"page={page}"])
                for repo in (data or {}).get("items", []):
                    if accepted >= args.per_lang:
                        break
                    if repo.get("fork") or repo["full_name"] in seen:
                        continue
                    seen.add(repo["full_name"])
                    rec = screen(repo, lang, q)
                    if rec.get("tier") in ("size-out", "too-few-src", "tree-failed"):
                        continue
                    rows.append(rec)
                    accepted += 1
                    print(f"  [{lang}] {rec['tier']:10s} {rec['repo']}", flush=True)
                    with _lock:
                        with open(args.out, "w", newline="") as f:
                            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
                            w.writeheader()
                            w.writerows(rows)
                time.sleep(2)

    print("\n=== verifiable candidates per language ===")
    for lang in [x.strip() for x in args.languages.split(",") if x.strip()]:
        sub = [r for r in rows if r["language"] == lang]
        ver = [r for r in sub if str(r.get("verifiable")) == "1"]
        ind = [r for r in sub if str(r.get("independent")) == "1"]
        tiers = {}
        for r in ver:
            tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
        print(f"  {lang:11s} screened {len(sub):4d}  verifiable {len(ver):4d}  "
              f"independent (bot or artefact) {len(ind):4d}  {tiers}")


if __name__ == "__main__":
    main()
