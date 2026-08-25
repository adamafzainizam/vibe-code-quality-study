#!/usr/bin/env python3
"""Extra show-and-tell artifacts for LinkedIn post #1 (and reusable for later posts).

Reads data/paired_stats.csv + data/matched_pairs_v2.csv, writes to posts/assets/.
"""
import csv
import os
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = "posts/assets"
os.makedirs(OUT, exist_ok=True)

INK = "#1a1a2e"
AI = "#0f766e"
CTRL = "#94a3b8"
GRID = "#e2e8f0"
ACCENT = "#b45309"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "text.color": INK,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "font.size": 13,
})

rows = list(csv.DictReader(open("data/paired_stats.csv")))
pairs = list(csv.DictReader(open("data/matched_pairs_v2.csv")))

# ---------- artifact 1: sample composition card ----------
from collections import Counter
tiers = Counter()
years = Counter()
for p in pairs:
    ev = p.get("ai_evidence", "")
    if ev.startswith("bot-contributor"):
        tiers["bot in commit history"] += 1
    elif ev == "readme-declaration":
        tiers["README declaration"] += 1
    else:
        tiers["search-query match"] += 1
    years[p.get("ai_year") or p["stratum"].split("|")[1]] += 1

fig, ax = plt.subplots(figsize=(9, 6.2))
ax.axis("off")
ax.set_position([0.05, 0.02, 0.9, 0.72])
fig.text(0.5, 0.945, "Inside the 46 pairs", ha="center",
         fontsize=20, fontweight="bold")
fig.text(0.5, 0.885, "How each AI-assisted repo proved it was AI-assisted",
         ha="center", fontsize=13, color="#475569")

total = sum(tiers.values())
labels = list(tiers.keys())
sizes = [tiers[l] for l in labels]
colors = [AI, "#14b8a6", CTRL]
wedges, _ = ax.pie(sizes, colors=colors, startangle=90,
                   wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2))
for w, l, s in zip(wedges, labels, sizes):
    angle = (w.theta2 + w.theta1) / 2
    x, y = np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))
    ax.annotate(f"{l}\n{s} repos ({s/total:.0%})",
                xy=(x * 0.79, y * 0.79), xytext=(x * 1.25, y * 1.18),
                ha="center", va="center", fontsize=13,
                arrowprops=dict(arrowstyle="-", color="#64748b", lw=1.2))
ax.text(0, 0, f"{total}\npairs", ha="center", va="center",
        fontsize=17, fontweight="bold")
fig.savefig(f"{OUT}/card_sample.png", dpi=200, bbox_inches="tight",
            facecolor="white")
plt.close(fig)

# ---------- artifact 2: p-value dot plot ----------
metrics = ["pct_cc_gt_10", "lizard_avg_ccn", "lizard_avg_nloc",
           "docstring_viols_per_kloc", "comment_ratio",
           "cc_mean", "mi_mean", "sloc"]
NAMES = {
    "pct_cc_gt_10": "% functions with complexity > 10",
    "lizard_avg_ccn": "average function complexity",
    "lizard_avg_nloc": "average function length",
    "docstring_viols_per_kloc": "docstring violations per 1,000 lines",
    "comment_ratio": "comment-to-code ratio",
    "cc_mean": "mean cyclomatic complexity (radon)",
    "mi_mean": "maintainability index (radon)",
    "sloc": "source lines of code",
}
import re
summary = open("data/summary.txt").read()
pvals = {}
for m in metrics:
    match = re.search(rf"^{m}:.*?Wil p=([0-9.]+)", summary, re.M)
    if match:
        pvals[m] = float(match.group(1))

fig, ax = plt.subplots(figsize=(9, 5.8))
names = [NAMES[m] for m in pvals]
pv = [pvals[m] for m in pvals]
y = list(range(len(pv)))[::-1]
ax.axvspan(0.05, 1.0, color="#f1f5f9", zorder=0)
ax.scatter(pv, y, s=230, color=AI, edgecolors=INK, linewidths=1.1, zorder=3)
for yi, p in zip(y, pv):
    ax.text(p, yi + 0.32, f"p={p:.2f}", ha="center", fontsize=11, color="#475569")
ax.set_yticks(y)
ax.set_yticklabels(names)
ax.set_xlabel("p-value (right of the line = no significant difference)",
              fontsize=12)
ax.axvline(0.05, color=ACCENT, lw=1.6, ls="--")
ax.text(0.052, -0.75, "significance line (0.05)", fontsize=11, color=ACCENT)
ax.set_xlim(-0.02, 1.0)
ax.set_ylim(-1.2, len(pv) - 0.3)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(f"{OUT}/chart_pvalues.png", dpi=200, facecolor="white")
plt.close(fig)

# ---------- artifact 3: quote card ----------
fig, ax = plt.subplots(figsize=(9, 5.2))
ax.axis("off")
fig.patch.set_facecolor("#0f172a")
ax.text(0.5, 0.62, '"I want AI to do my laundry\nso I can make art."',
        transform=ax.transAxes, ha="center", va="center",
        fontsize=25, fontweight="bold", color="white", linespacing=1.5)
ax.text(0.5, 0.30, "Not AI making art so I can do laundry.",
        transform=ax.transAxes, ha="center", fontsize=17,
        color="#5eead4", style="italic")
fig.savefig(f"{OUT}/card_quote.png", dpi=200, bbox_inches="tight",
            facecolor="#0f172a")
plt.close(fig)

# ---------- artifact 4: attrition waterfall ----------
fig, ax = plt.subplots(figsize=(9, 5.2))
stages = [
    ("50 matched pairs\n(v1 sample)", 50, "#334155"),
    ("both repos had\nrecognized license", 16, AI),
    ("backfilled with\nsame-stratum swaps", 46, "#14b8a6"),
]
xs = range(len(stages))
for x, (label, v, c) in zip(xs, stages):
    ax.bar(x, v, color=c, width=0.55, edgecolor=INK, linewidth=1.1)
    ax.text(x, v + 1.2, str(v), ha="center", fontsize=17, fontweight="bold")
    ax.text(x, -8.5, label, ha="center", fontsize=12)
ax.annotate("license gate removed\n68% of the sample", xy=(1, 20),
            xytext=(1.0, 36), fontsize=12, color=ACCENT, ha="center",
            arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=1.5))
ax.annotate("backfill restored\nthe sample", xy=(2.25, 46), xytext=(2.25, 55),
            fontsize=12, color=ACCENT, ha="center",
            arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=1.5))
ax.set_xticks([])
ax.set_ylim(0, 60)
ax.set_ylabel("usable pairs")
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", color=GRID, lw=0.8)
ax.set_axisbelow(True)
fig.subplots_adjust(bottom=0.22)
fig.tight_layout()
fig.savefig(f"{OUT}/chart_attrition.png", dpi=200, facecolor="white")
plt.close(fig)

print("wrote:", sorted(os.listdir(OUT)))
