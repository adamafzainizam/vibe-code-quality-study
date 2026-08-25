#!/usr/bin/env python3
"""Charts for LinkedIn posts about the vibe-coding quality study.

Reads data/paired_stats.csv + data/matched_pairs_v2.csv, writes PNGs to
posts/assets/. Clean, high-contrast style that survives LinkedIn compression.
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "posts/assets"
os.makedirs(OUT, exist_ok=True)

INK = "#1a1a2e"      # near-black for text
AI = "#0f766e"       # teal - AI arm
CTRL = "#94a3b8"     # grey - control arm
GRID = "#e2e8f0"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "text.color": INK,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "font.size": 13,
})

# ---------- load paired stats ----------
rows = list(csv.DictReader(open("data/paired_stats.csv")))
pairs = list(csv.DictReader(open("data/matched_pairs_v2.csv")))


def vals(row_prefix):
    out = {}
    for r in rows:
        m = r["metric"]
        a = r[f"{row_prefix}_{m}"]
        if a != "":
            out.setdefault(m, []).append(float(a))
    return out


ai_v = {m: [float(r[f"ai_{m}"]) for r in rows if r[f"ai_{m}"] != ""]
        for m in rows[0] if False}
metrics = ["pct_cc_gt_10", "lizard_avg_ccn", "lizard_avg_nloc",
           "docstring_viols_per_kloc", "comment_ratio"]

# medians straight from summary values recomputed here
import statistics as st
medians = {}
for m in metrics:
    ai_vals, c_vals = [], []
    for p in rows:
        av, cv = p[f"ai_{m}"], p[f"ctrl_{m}"]
        if av != "" and cv != "":
            ai_vals.append(float(av))
            c_vals.append(float(cv))
    medians[m] = (st.median(ai_vals), st.median(c_vals))

LABELS = {
    "pct_cc_gt_10": "% of functions with\ncomplexity > 10",
    "lizard_avg_ccn": "average function\ncomplexity",
    "lizard_avg_nloc": "average function\nlength (lines)",
    "docstring_viols_per_kloc": "docstring violations\nper 1,000 lines",
    "comment_ratio": "comment-to-code\nratio (%)",
}
PCT = {"comment_ratio"}  # stored as fraction, display as %


def display(m, v):
    return v * 100 if m in PCT else v


# ---------- chart 1: dumbbell / paired medians ----------
fig, ax = plt.subplots(figsize=(9, 6.4))
y = list(range(len(metrics)))[::-1]
for i, m in zip(y, metrics):
    a, c = display(m, medians[m][0]), display(m, medians[m][1])
    ax.plot([c, a], [i, i], color=GRID, lw=3.5, zorder=1)
    ax.scatter([c], [i], s=210, color=CTRL, zorder=2, edgecolors=INK, linewidths=1.1)
    ax.scatter([a], [i], s=210, color=AI, zorder=3, edgecolors=INK, linewidths=1.1)
ax.set_yticks(y)
ax.set_yticklabels([LABELS[m] for m in metrics])
ax.set_xlabel("median value per repo")
handles = [
    plt.Line2D([], [], marker="o", ls="", color=CTRL, markersize=12, label="traditionally written"),
    plt.Line2D([], [], marker="o", ls="", color=AI, markersize=12, label="vibe-coded"),
]
ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=13)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(f"{OUT}/chart_medians.png", dpi=200)
plt.close(fig)

# ---------- chart 2: % of pairs where AI arm lower ----------
wins = {}
for m in metrics:
    lower = higher = 0
    for p in rows:
        d = p.get(f"delta_{m}", "")
        if d == "":
            continue
        dv = float(d)
        dv = dv * 100 if m in PCT else dv
        if abs(dv) < 1e-12:
            continue
        if (dv < 0) != (m in PCT):  # comment_ratio: higher = AI "better"
            lower += 1
        else:
            higher += 1
    wins[m] = lower / max(lower + higher, 1) * 100

fig, ax = plt.subplots(figsize=(9, 5.6))
names = [LABELS[m].replace("\n", " ") for m in metrics]
pcts = [wins[m] for m in metrics]
colors = [AI if v >= 50 else CTRL for v in pcts]
bars = ax.barh(names[::-1], pcts[::-1], color=colors[::-1], height=0.62,
               edgecolor=INK, linewidth=1.0)
ax.axvline(50, color=INK, lw=1.4, ls="--")
ax.text(51, len(metrics) - 0.45, "50%", fontsize=11, color=INK)
for b, v in zip(bars, pcts[::-1]):
    ax.text(v + 1.5, b.get_y() + b.get_height() / 2, f"{v:.0f}%",
            va="center", fontsize=12, color=INK)
ax.set_xlim(0, 100)
ax.set_xlabel("share of matched pairs where the vibe-coded repo scores better")
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(f"{OUT}/chart_winrate.png", dpi=200)
plt.close(fig)

# ---------- chart 3: methodology flow ----------
fig, ax = plt.subplots(figsize=(10, 4.2))
ax.axis("off")
steps = [
    ("Search GitHub", "vibe-coded Python repos:\nbot contributors,\nREADME declarations"),
    ("Match pairs", "same LOC band,\nyear, star band\n(seed 24070145)"),
    ("Measure blind", "clone + radon, lizard,\ndocstring checks;\narm labels withheld"),
    ("Compare pairs", "46 pairs,\nWilcoxon signed-rank\n+ effect sizes"),
]
w, h = 0.215, 0.62
xs = [0.02, 0.27, 0.52, 0.77]
for x, (title, body) in zip(xs, steps):
    box = plt.Rectangle((x, 0.18), w, h, transform=ax.transAxes,
                        facecolor="#f8fafc", edgecolor=INK, lw=1.4)
    ax.add_patch(box)
    ax.text(x + w / 2, 0.68, title, transform=ax.transAxes, ha="center",
            fontsize=14, fontweight="bold")
    ax.text(x + w / 2, 0.40, body, transform=ax.transAxes, ha="center",
            fontsize=11.5, va="center")
for x in xs[:-1]:
    ax.annotate("", xy=(x + w + 0.028, 0.49), xytext=(x + w + 0.005, 0.49),
                xycoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.6))
fig.tight_layout()
fig.savefig(f"{OUT}/chart_method.png", dpi=200)
plt.close(fig)

print("wrote:", os.listdir(OUT))
