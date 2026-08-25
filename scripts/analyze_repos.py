#!/usr/bin/env python3
"""Analysis pipeline stage A: clone each repo, verify license, compute metrics.

Reads data/matched_pairs.csv and processes BOTH arms' repos into one flat
metrics file keyed by repo full_name only (arm-blind: the arm/pair mapping
stays in matched_pairs.csv and is joined at aggregation time).

Per repo:
  1. License check via GitHub API (recognized OSS license required).
     Repos without one are recorded as skipped, not analyzed.
  2. Shallow clone into .clone-cache/.
  3. Metrics over qualifying .py files (same exclusions as compute_loc.py):
     - radon raw: loc, sloc, comments, docstrings
     - radon cc: mean/max cyclomatic complexity, % functions CC > 10
     - radon MI: mean/min maintainability index
     - lizard: function count, avg NLOC, avg/max cyclomatic complexity,
       avg tokens per function
     - pydocstyle CLI (pep257): violation count normalized per kSLOC

Appends to data/metrics_raw.csv (resumable; skips repos already status=ok).
Usage:
    GITHUB_TOKEN=... .venv/bin/python scripts/analyze_repos.py \
        --pairs data/matched_pairs.csv --out data/metrics_raw.csv
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

CACHE = ".clone-cache"

RECOGNIZED_LICENSES = {
    "mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause",
    "gpl-3.0", "mpl-2.0", "unlicense", "isc", "lgpl-3.0",
}

PY_EXCLUDE = re.compile(
    r"(^|/)(\.venv|venv|site-packages|\.git|build|dist|__pycache__|node_modules)(/|$)")

METRIC_FIELDS = [
    "repo", "license_key", "status",
    "n_py_files", "loc", "sloc", "comment_lines", "docstring_lines",
    "cc_mean", "cc_max", "pct_cc_gt_10",
    "mi_mean", "mi_min",
    "n_functions", "lizard_avg_nloc", "lizard_avg_ccn", "lizard_max_ccn",
    "avg_tokens_per_func",
    "docstring_violations", "docstring_viols_per_kloc",
]


def gh_json(url, token):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "vibe-code-quality-study",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                return None
            time.sleep(5 * (attempt + 1))


def clone(full, token):
    dest = os.path.join(CACHE, full.replace("/", "__"))
    if os.path.isdir(dest):
        return dest, "cached"
    url = f"https://{token}@github.com/{full}.git" if token else f"https://github.com/{full}.git"
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        r = subprocess.run(["git", "clone", "--depth", "1", "--quiet", url, dest],
                           capture_output=True, text=True, timeout=300, env=env)
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest, ignore_errors=True)
        return None, "clone-timeout"
    if r.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        return None, r.stderr.strip().splitlines()[-1] if r.stderr else "clone-failed"
    return dest, "ok"


def py_files(dest):
    out = []
    for root, dirs, files in os.walk(dest):
        rel_root = os.path.relpath(root, dest)
        dirs[:] = [d for d in dirs
                   if not PY_EXCLUDE.search(os.path.join(rel_root, d))]
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(root, f))
    return out


def analyze_repo(files, venv_bin):
    """Run all static tools over the repo's .py files."""
    import radon.raw
    import radon.complexity as rc
    import radon.metrics as rm
    import lizard

    m = {k: "" for k in METRIC_FIELDS}
    m["n_py_files"] = len(files)

    cc_vals, mi_vals = [], []
    for fp in files:
        try:
            src = open(fp, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        # raw counts
        try:
            raw = radon.raw.analyze(src)
            m["loc"] = (m["loc"] or 0) + raw.loc
            m["sloc"] = (m["sloc"] or 0) + raw.sloc
            m["comment_lines"] = (m["comment_lines"] or 0) + raw.comments
            m["docstring_lines"] = (m["docstring_lines"] or 0) + raw.multi
        except SyntaxError:
            continue
        # cyclomatic complexity
        try:
            cc_vals += [b.complexity for b in rc.cc_visit(src)]
        except Exception:
            pass
        # maintainability index
        try:
            mv = rm.mi_visit(src, multi=True)
            if mv is not None:
                mi_vals.append(mv)
        except Exception:
            pass

    if cc_vals:
        m["cc_mean"] = round(sum(cc_vals) / len(cc_vals), 3)
        m["cc_max"] = max(cc_vals)
        m["pct_cc_gt_10"] = round(100 * sum(1 for c in cc_vals if c > 10) / len(cc_vals), 2)
    if mi_vals:
        m["mi_mean"] = round(sum(mi_vals) / len(mi_vals), 2)
        m["mi_min"] = round(min(mi_vals), 2)

    # lizard
    try:
        res = list(lizard.analyze(files, threads=4))
        all_funcs = [f for fi in res for f in fi.function_list]
        n = len(all_funcs)
        m["n_functions"] = n
        if n:
            m["lizard_avg_nloc"] = round(sum(f.nloc for f in all_funcs) / n, 2)
            m["lizard_avg_ccn"] = round(sum(f.cyclomatic_complexity for f in all_funcs) / n, 3)
            m["lizard_max_ccn"] = max(f.cyclomatic_complexity for f in all_funcs)
            m["avg_tokens_per_func"] = round(sum(f.length for f in all_funcs) / n, 1)
    except Exception as e:
        print(f"  lizard failed: {e}", file=sys.stderr)

    # pydocstyle via CLI (stable interface); cap file list at 400 to bound runtime
    viols = ""
    try:
        sel = files[:400]
        r = subprocess.run(
            [os.path.join(venv_bin, "pydocstyle"), "--convention=pep257"] + sel,
            capture_output=True, text=True, timeout=600)
        viols = len(re.findall(r":\s*D\d+", r.stdout))
    except Exception as e:
        print(f"  pydocstyle failed: {e}", file=sys.stderr)
    m["docstring_violations"] = viols
    if isinstance(m["loc"], int) and m["loc"]:
        m["docstring_viols_per_kloc"] = round(1000 * viols / m["loc"], 2)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="data/matched_pairs.csv")
    ap.add_argument("--out", default="data/metrics_raw.csv")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    venv_bin = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin")

    pairs = list(csv.DictReader(open(args.pairs)))
    repos, seen = [], set()
    for p in pairs:
        for col in ("ai_repo", "ctrl_repo"):
            if p[col] not in seen:
                seen.add(p[col])
                repos.append(p[col])

    done = set()
    write_header = not os.path.exists(args.out) or os.path.getsize(args.out) == 0
    if not write_header:
        for r in csv.DictReader(open(args.out)):
            if r.get("status") == "ok":
                done.add(r["repo"])

    out_f = open(args.out, "a", newline="")
    w = csv.DictWriter(out_f, fieldnames=METRIC_FIELDS)
    if write_header:
        w.writeheader()

    for i, full in enumerate(repos):
        if full in done:
            print(f"[{i+1}/{len(repos)}] skip {full} (done)")
            continue
        info = gh_json(f"https://api.github.com/repos/{full}", token)
        lic = (info or {}).get("license") or {}
        lic_key = (lic.get("spdx_id") or "none")
        lic_norm = lic_key.lower() if lic_key else "none"
        if info is None:
            row = {"repo": full, "license_key": "?", "status": "error:api"}
        elif lic_norm not in RECOGNIZED_LICENSES:
            row = {"repo": full, "license_key": lic_key, "status": "skipped:license"}
        else:
            row_license = {"repo": full, "license_key": lic_norm}
            dest, status = clone(full, token)
            if dest is None:
                row = {**row_license, "status": f"error:{status[:60]}"}
            else:
                print(f"[{i+1}/{len(repos)}] analyze {full}", flush=True)
                try:
                    m = analyze_repo(py_files(dest), venv_bin)
                    row = {**{k: v for k, v in m.items() if k not in ("repo", "license_key", "status")}, **row_license, "status": "ok"}
                except Exception as e:
                    print(f"  ERROR {full}: {e}", file=sys.stderr)
                    row = {**row_license,
                           "status": f"error:{type(e).__name__}"}
                finally:
                    shutil.rmtree(dest, ignore_errors=True)
        w.writerow(row)
        out_f.flush()
        time.sleep(0.7)

    out_f.close()
    rows = list(csv.DictReader(open(args.out)))
    okc = sum(1 for r in rows if r["status"] == "ok")
    print(f"\ndone: {okc}/{len(repos)} analyzed -> {args.out}")


if __name__ == "__main__":
    main()
