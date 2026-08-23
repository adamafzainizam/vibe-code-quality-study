#!/usr/bin/env python3
"""Collect candidate repos for the vibe-code quality study.

Queries GitHub Search API for self-declared AI-assisted ("vibe-coded") Python
repos and applies structural filters to keep only real applications:
  - >= MIN_PY source .py files (excluding tests? no: tests count as signal)
  - python is dominant language
  - not a docs/prompt collection

Usage:
    python3 collect_candidates.py --queries queries.txt --out candidates.csv
Requires GITHUB_TOKEN env var for decent rate limits (optional but recommended).
"""
import argparse
import base64
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.parse

API = "https://api.github.com"
MIN_STARS = int(os.environ.get("MIN_STARS", "1"))
MAX_SIZE_KB = int(os.environ.get("MAX_SIZE_KB", "50000"))
MIN_SIZE_KB = int(os.environ.get("MIN_SIZE_KB", "50"))


def gh_request(path, token=None, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                wait = int(e.headers.get("X-RateLimit-Reset", time.time() + 60))
                sleep = max(wait - time.time(), 5) + 2
                print(f"  rate limited; sleeping {sleep:.0f}s", file=sys.stderr)
                time.sleep(min(sleep, 700))
            else:
                raise
    raise RuntimeError("rate limit retries exhausted")


def search_repos(query, token, max_pages=3):
    items = []
    for page in range(1, max_pages + 1):
        data = gh_request("/search/repositories", token,
                          {"q": query, "per_page": 100, "page": page,
                           "sort": "updated", "order": "desc"})
        items.extend(data.get("items", []))
        if len(data.get("items", [])) < 100:
            break
        time.sleep(7)  # search API: 10 req/min unauth
    return items


def passes_structural_filter(repo, token):
    """Check a repo looks like a Python app, not a prompt/docs collection."""
    full = repo["full_name"]
    lang = (repo.get("language") or "").lower()
    if lang != "python":
        return False, "language != python"
    size = repo["size"]
    if not (MIN_SIZE_KB <= size <= MAX_SIZE_KB):
        return False, f"size {size}KB outside [{MIN_SIZE_KB},{MAX_SIZE_KB}]"
    if repo["stargazers_count"] < MIN_STARS:
        return False, "too few stars (likely spam/empty)"

    tree = gh_request(f"/repos/{full}/git/trees/{repo['default_branch']}?recursive=1", token)
    paths = [t["path"] for t in tree.get("tree", []) if t["type"] == "blob"]
    py = [p for p in paths if p.endswith(".py") and ".venv" not in p and "site-packages" not in p]
    md_yaml = [p for p in paths if p.endswith((".md", ".yaml", ".yml", ".txt", ".jsonl"))]
    if len(py) < 5:
        return False, f"only {len(py)} py files"
    if len(md_yaml) > len(py):
        return False, f"docs/prompt-heavy ({len(md_yaml)} md/yaml vs {len(py)} py)"

    # README declaration check (AI tool mention)
    readme_path = next((p for p in paths if p.lower() in ("readme.md", "readme.rst", "readme.txt")), None)
    declared = False
    readme_excerpt = ""
    if readme_path:
        try:
            data = gh_request(f"/repos/{full}/contents/{readme_path}", token)
            content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
            readme_excerpt = content[:500]
            pattern = re.compile(
                r"\b(vibe.?cod|built with|generated with|created using|developed using)"
                r"[^\n]{0,40}\b(cursor|claude|copilot|chatgpt|gpt-?4|gpt-?5|gemini|deepseek|llm)\b",
                re.IGNORECASE)
            declared = bool(pattern.search(content))
        except Exception:
            pass
    return True, ("declared-ai" if declared else "no-readme-declaration")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default="queries.txt")
    ap.add_argument("--out", default="data/candidates.csv")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    with open(args.queries) as f:
        queries = [q.strip() for q in f if q.strip() and not q.startswith("#")]

    seen = set()
    rows = []
    out_exists = os.path.exists(args.out)
    if out_exists:
        with open(args.out) as f:
            for r in csv.DictReader(f):
                seen.add(r["full_name"])
                rows.append(r)

    for q in queries:
        print(f"== query: {q}")
        for repo in search_repos(q, token):
            full = repo["full_name"]
            if full in seen:
                continue
            seen.add(full)
            ok, reason = passes_structural_filter(repo, token)
            row = {
                "full_name": full,
                "query": q,
                "stars": repo["stargazers_count"],
                "size_kb": repo["size"],
                "created": repo["created_at"][:10],
                "pushed": repo["pushed_at"][:10],
                "url": repo["html_url"],
                "passed_filter": ok,
                "reason": reason,
                "arm": "ai-assisted",
            }
            rows.append(row)
            print(f"  {'PASS' if ok else 'skip'} {full} ({reason})")
            time.sleep(1)

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    passed = sum(1 for r in rows if r["passed_filter"])
    print(f"\nTotal unique candidates: {len(rows)}, passed filter: {passed}")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
