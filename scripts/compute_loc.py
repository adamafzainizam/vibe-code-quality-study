#!/usr/bin/env python3
"""Phase 1 of matching: shallow-clone repos and compute source-LOC bands.

Reads a CSV with columns (full_name, ...) — one row per accepted repo —
shallow-clones each into .clone-cache/, counts non-blank source lines across
qualifying .py files (excludes venv/site-packages/tests? NO — tests kept,
per docs/control-group-criteria.md size = source .py LOC), and writes
<out> with added columns: src_loc, loc_band.

LOC band definition (docs/control-group-criteria.md):
    <1k, 1k-5k, 5k-20k, >20k

Usage:
    GITHUB_TOKEN=... python3 scripts/compute_loc.py \
        --in data/controls_accepts.csv --col full_name --out data/controls_loc.csv
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys

CACHE = ".clone-cache"


def loc_band(n):
    if n < 1000:
        return "<1k"
    if n < 5000:
        return "1k-5k"
    if n < 20000:
        return "5k-20k"
    return ">20k"


def clone(full, token):
    dest = os.path.join(CACHE, full.replace("/", "__"))
    if os.path.isdir(dest):
        return dest, "cached"
    url = f"https://{token}@github.com/{full}.git" if token else f"https://github.com/{full}.git"
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", url, dest],
            capture_output=True, text=True, timeout=300, env=env)
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest, ignore_errors=True)
        return None, "clone-timeout"
    if r.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        return None, r.stderr.strip().splitlines()[-1] if r.stderr else "clone-failed"
    return dest, "ok"


PY_EXCLUDE = re.compile(r"(^|/)(\.venv|venv|site-packages|\.git|build|dist|__pycache__|node_modules)(/|$)")


def source_loc(dest):
    total = 0
    nfiles = 0
    for root, dirs, files in os.walk(dest):
        dirs[:] = [d for d in dirs if not PY_EXCLUDE.search(os.path.join(root, d).replace(dest, "", 1))]
        for f in files:
            if not f.endswith(".py"):
                continue
            nfiles += 1
            try:
                with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                    total += sum(1 for line in fh if line.strip())
            except OSError:
                pass
    return total, nfiles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--col", default="full_name")
    ap.add_argument("--out", required=True)
    ap.add_argument("--filter-col", default=None,
                    help="only process rows where this column == --filter-val")
    ap.add_argument("--filter-val", default=None)
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")

    rows = list(csv.DictReader(open(args.inp)))
    if args.filter_col:
        rows = [r for r in rows if r[args.filter_col] == args.filter_val]

    fields = list(rows[0].keys()) if rows else []
    for extra in ("src_loc", "py_files", "loc_band", "loc_status"):
        if extra not in fields:
            fields.append(extra)

    done = {}
    if os.path.exists(args.out):
        for r in csv.DictReader(open(args.out)):
            if r.get("loc_status") == "ok":
                done[r[args.col]] = r

    out_f = open(args.out, "w", newline="")
    w = csv.DictWriter(out_f, fieldnames=fields)
    w.writeheader()

    ok = fail = 0
    for i, row in enumerate(rows):
        full = row[args.col]
        if full in done:
            w.writerow({**row, **{k: done[full][k] for k in ("src_loc", "py_files", "loc_band", "loc_status")}})
            ok += 1
            continue
        dest, status = clone(full, token)
        if dest is None:
            row.update(src_loc="", py_files="", loc_band="", loc_status=f"error:{status[:80]}")
            w.writerow(row); out_f.flush()
            fail += 1
            print(f"[{i+1}/{len(rows)}] FAIL {full} ({status[:60]})", file=sys.stderr)
            continue
        loc, nf = source_loc(dest)
        row.update(src_loc=loc, py_files=nf, loc_band=loc_band(loc), loc_status="ok")
        w.writerow(row); out_f.flush()
        shutil.rmtree(dest, ignore_errors=True)  # keep cache small
        ok += 1
        print(f"[{i+1}/{len(rows)}] ok {full} loc={loc} band={row['loc_band']}")

    out_f.close()
    print(f"\ndone: {ok} ok, {fail} failed -> {args.out}")


if __name__ == "__main__":
    main()
