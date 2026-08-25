# Vibe-Coded vs Traditional Code Quality Study

Empirical comparison of static-analysis quality metrics between self-declared
AI-assisted ("vibe-coded") public GitHub repos and matched traditionally-written repos.

**Headline result (n=46 pairs): no statistically significant difference on any
static metric tested (all Wilcoxon p > 0.10). Directional trends favored the
AI-assisted arm: lower complexity, fewer docstring violations per kLOC, higher
comment ratio.**

## Reproducibility

The full pipeline is scripted:

1. `collect_controls.py` — GitHub Search API collection of control candidates
2. `compute_loc.py` + `match_sample.py` — stratified matching (LOC band × year × star band), fixed RNG seed
3. `analyze_repos.py` — per-repo metrics (radon CC/MI, lizard, docstrings), license-gated, arm-blind
4. `backfill_pairs.py` — same-stratum replacement after attrition
5. `aggregate_stats.py` — paired Wilcoxon + paired t + rank-biserial r

Data files live in `data/`. The RNG seed used for matching is a fixed constant;
it is recorded privately by the author to keep personal identifiers out of this
public repo. Any fixed seed reproduces the same pipeline; re-running with your
own seed will produce a slightly different but statistically equivalent sample.

## Caveats

- Pilot sample: 46 pairs.
- Selection effect: AI-arm repos self-declared AI use (bot commits or README).
- Static metrics only — correctness not tested.
- License gate removed 40% of first-batch repos before matching.

## License

MIT
