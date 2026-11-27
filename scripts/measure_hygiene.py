#!/usr/bin/env python3
"""Arm-blind hygiene measurement: the things radon and lizard cannot see.

The study's metrics are complexity and documentation proxies. They say nothing
about whether a repository has tests, CI, dependency declarations, type hints or
a bare `except:`. Those are the properties a reviewer would actually check, and
they are cheap to measure from a shallow clone.

Discipline is the same as analyze_repos.py: this script never reads which arm a
repository belongs to. It takes the flat set of repository names out of the
pairs file, measures each, and writes one row per repo keyed by name. The arm
join happens later, in hygiene_stats.py, after all measurement is done.

      data/hygiene_metrics.csv   one row per repo, arm-blind

Usage:
    .venv/bin/python scripts/measure_hygiene.py \
        --pairs data/matched_pairs_v2.csv --out data/hygiene_metrics.csv
"""
import argparse
import ast
import csv
import os
import re
import shutil
import subprocess
import sys

CACHE = ".hygiene-cache"
EXCLUDE = re.compile(
    r"(^|/)(\.venv|venv|site-packages|\.git|build|dist|__pycache__|node_modules|\.tox)(/|$)")
TEST_FILE = re.compile(r"(^|/)(tests?|testing)/|(^|/)(test_.*\.py|.*_test\.py|conftest\.py)$")

FIELDS = [
    "repo", "status", "n_py_files", "n_py_loc",
    "n_parse_fail", "parse_fail_rate",
    "has_tests", "n_test_files", "n_test_funcs", "test_loc_ratio",
    "has_ci", "n_workflows",
    "has_pyproject", "has_requirements", "has_lockfile", "has_packaging",
    "n_defs", "typed_defs", "type_hint_coverage",
    "n_func_docstrings", "func_docstring_coverage",
    "n_bare_except", "n_broad_except", "bare_except_per_kloc", "broad_except_per_kloc",
    "n_print", "n_logging", "print_per_kloc",
    "n_assert", "assert_per_kloc",
    "n_eval_exec", "n_shell_true", "n_todo_fixme",
]


def clone(full):
    dest = os.path.join(CACHE, full.replace("/", "__"))
    if os.path.isdir(dest):
        return dest
    os.makedirs(CACHE, exist_ok=True)
    url = f"https://github.com/{full}.git"
    try:
        subprocess.run(["git", "clone", "--depth", "1", "--quiet", url, dest],
                       check=True, timeout=180,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return dest
    except Exception:
        return None


def py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        if EXCLUDE.search(dirpath + "/"):
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                p = os.path.join(dirpath, fn)
                yield os.path.relpath(p, root).replace(os.sep, "/"), p


def walk_ast(tree):
    """Count the constructs we care about."""
    defs, typed, docs = 0, 0, 0
    bare = broad = prints = logs = asserts = evals = shell = todos = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs += 1
            args = node.args
            annotated = any(a.annotation is not None for a in
                            args.posonlyargs + args.args + args.kwonlyargs)
            annotated = annotated or (args.vararg is not None and args.vararg.annotation is not None)
            if annotated:
                typed += 1
            if ast.get_docstring(node):
                docs += 1
        elif isinstance(node, ast.ExceptHandler):
            if node.type is None:
                bare += 1
            elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
                broad += 1
        elif isinstance(node, ast.Call):
            f = node.func
            name = getattr(f, "id", None) or getattr(f, "attr", None)
            if name == "print":
                prints += 1
            elif name in ("eval", "exec"):
                evals += 1
            for kw in node.keywords or []:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    shell += 1
        elif isinstance(node, ast.Assert):
            asserts += 1
        elif isinstance(node, ast.Attribute):
            if node.attr in ("info", "debug", "warning", "error", "exception") and \
                    isinstance(node.value, ast.Name) and node.value.id in ("logging", "logger", "log"):
                logs += 1
    return dict(defs=defs, typed=typed, docs=docs, bare=bare, broad=broad,
                prints=prints, logs=logs, asserts=asserts, evals=evals, shell=shell)


def measure(full):
    root = clone(full)
    if not root:
        return {"repo": full, "status": "clone-failed"}
    files = list(py_files(root))
    if not files:
        return {"repo": full, "status": "no-py"}

    n_loc = fails = test_files = test_funcs = test_loc = 0
    tot = dict(defs=0, typed=0, docs=0, bare=0, broad=0, prints=0, logs=0, asserts=0, evals=0, shell=0)
    todos = 0
    for rel, path in files:
        try:
            src = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            fails += 1
            continue
        lines = src.count("\n") + 1
        n_loc += lines
        todos += len(re.findall(r"\b(TODO|FIXME|XXX)\b", src))
        is_test = bool(TEST_FILE.search(rel))
        if is_test:
            test_files += 1
            test_loc += lines
        try:
            tree = ast.parse(src)
        except SyntaxError:
            fails += 1
            continue
        c = walk_ast(tree)
        for k in tot:
            tot[k] += c[k]
        if is_test:
            test_funcs += sum(
                1 for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name.startswith("test"))

    kloc = max(n_loc / 1000.0, 1e-9)
    has_workflows = os.path.isdir(os.path.join(root, ".github", "workflows"))
    n_workflows = len(os.listdir(os.path.join(root, ".github", "workflows"))) if has_workflows else 0
    locks = any(os.path.exists(os.path.join(root, f)) for f in
                ("poetry.lock", "uv.lock", "Pipfile.lock", "pdm.lock"))
    return {
        "repo": full, "status": "ok", "n_py_files": len(files), "n_py_loc": n_loc,
        "n_parse_fail": fails, "parse_fail_rate": round(fails / max(len(files), 1), 4),
        "has_tests": int(test_files > 0), "n_test_files": test_files,
        "n_test_funcs": test_funcs, "test_loc_ratio": round(test_loc / max(n_loc, 1), 4),
        "has_ci": int(has_workflows), "n_workflows": n_workflows,
        "has_pyproject": int(os.path.exists(os.path.join(root, "pyproject.toml"))),
        "has_requirements": int(os.path.exists(os.path.join(root, "requirements.txt"))),
        "has_lockfile": int(locks),
        "has_packaging": int(any(os.path.exists(os.path.join(root, f)) for f in
                                 ("pyproject.toml", "setup.py", "requirements.txt"))),
        "n_defs": tot["defs"], "typed_defs": tot["typed"],
        "type_hint_coverage": round(tot["typed"] / max(tot["defs"], 1), 4),
        "n_func_docstrings": tot["docs"],
        "func_docstring_coverage": round(tot["docs"] / max(tot["defs"], 1), 4),
        "n_bare_except": tot["bare"], "n_broad_except": tot["broad"],
        "bare_except_per_kloc": round(tot["bare"] / kloc, 3),
        "broad_except_per_kloc": round(tot["broad"] / kloc, 3),
        "n_print": tot["prints"], "n_logging": tot["logs"],
        "print_per_kloc": round(tot["prints"] / kloc, 3),
        "n_assert": tot["asserts"], "assert_per_kloc": round(tot["asserts"] / kloc, 3),
        "n_eval_exec": tot["evals"], "n_shell_true": tot["shell"], "n_todo_fixme": todos,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="data/matched_pairs_v2.csv")
    ap.add_argument("--out", default="data/hygiene_metrics.csv")
    args = ap.parse_args()

    pairs = list(csv.DictReader(open(args.pairs)))
    repos = sorted({r["ai_repo"] for r in pairs} | {r["ctrl_repo"] for r in pairs})
    done = {}
    if os.path.exists(args.out):
        for r in csv.DictReader(open(args.out)):
            done[r["repo"]] = r
        print(f"resuming: {len(done)} repos already measured", flush=True)

    def save():
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(done.values())

    for i, full in enumerate(repos, 1):
        if full in done and done[full]["status"] == "ok":
            continue
        rec = measure(full)
        done[full] = rec
        save()
        print(f"[{i}/{len(repos)}] {rec['status']:12s} {full}", flush=True)

    tried = [r for r in done.values() if r.get("status") != "no-py"]
    shutil.rmtree(CACHE, ignore_errors=True)
    ok = sum(1 for r in tried if r["status"] == "ok")
    print(f"\nmeasured {ok}/{len(repos)} repos -> {args.out}", flush=True)
    if ok < len(repos):
        print("failures: " + ", ".join(r['repo'] for r in tried if r['status'] != 'ok'),
              file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
