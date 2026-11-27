# Vibe-Coded vs Traditional Code Quality Study

Empirical comparison of static-analysis quality metrics between self-declared
AI-assisted ("vibe-coded") public GitHub repos and matched traditionally-written repos.

**Headline result (n=46 pairs): no statistically significant difference on any
static metric tested (all Wilcoxon p > 0.10). Directional trends favored the
AI-assisted arm: lower complexity, fewer docstring violations per kLOC, higher
comment ratio.**

Scope, stated up front, because that headline means less than it looks: at 46 pairs
the design detects only a large difference (minimum detectable `|d_z|` of 0.44 at 80%
power, and 50% power at 0.3), 62% of the AI arm carries no trace of an agent under
either instrument, and about a fifth of the control arm ships AI tooling files and is
probably not a control. All of that is quantified in
[the second pass](./docs/second-pass-2026-11-27.md), with a paired
engineering-hygiene comparison, the licence base rate the first analysis never
measured, and the dilution arithmetic.

## Reproducibility

The full pipeline is scripted:

1. `collect_controls.py`: GitHub Search API collection of control candidates
2. `compute_loc.py` + `match_sample.py`: stratified matching (LOC band × year × star band), fixed RNG seed
3. `analyze_repos.py`: per-repo metrics (radon CC/MI, lizard, docstrings), license-gated, arm-blind
4. `backfill_pairs.py`: same-stratum replacement after attrition
5. `aggregate_stats.py`: paired Wilcoxon + paired t + rank-biserial r

Second pass, added 27 November 2026:

6. `power_analysis.py`: standardised paired effect with bootstrap CI, simulated minimum detectable effect, pairs needed per effect size
7. `measure_hygiene.py`: tests, CI, packaging, type hints, exception handling and parse failures, from a shallow clone, arm-blind
8. `hygiene_stats.py`: exact McNemar for practices, paired Wilcoxon for rates, BH-FDR within each family
9. `collect_license_base_rate.py`: the traditional arm re-collected with no licence gate
10. `license_base_rate_analysis.py`: licence presence by arm, Fisher exact, stratified by star and size band
11. `detect_ai_artifacts.py`: committed AI-tooling artefacts (rule sets, instruction files, MCP configs) as a second evidence instrument, arm-blind
12. `artifact_evidence_stats.py`: artefact rates per evidence tier, contamination of the control arm, and the dilution bound it implies

Data files live in `data/`. The RNG seed used for matching is a fixed constant;
it is recorded privately by the author to keep personal identifiers out of this
public repo. Any fixed seed reproduces the same pipeline; re-running with your
own seed will produce a slightly different but statistically equivalent sample.

## Caveats

- Pilot sample: 46 pairs. Enough for a large effect, not for a medium one.
- Selection effect: 85% of the AI arm has no commit or README evidence, and 62% has no trace at all once committed AI-tooling files are counted too. Only 9.4% carries an AI-agent commit. Absence of a trace is not absence of AI use, since agents often run under the developer's own Git identity, and some authors scrub traces deliberately.
- Contaminated controls: 20.6% of the control arm ships a strong AI-tooling artefact (.cursorrules, .claude/, Copilot instructions and so on), so under the study's own definition they are not controls. Two-sided misclassification dilutes a real difference by about (1 - c - f); at the measured c the true effect is up to 1.26x to 1.7x the measured one.
- Static metrics only, so correctness is not tested. The hygiene pass adds tests, CI and typing as proxies and finds no difference either.
- The first run's licence attrition was one-sided by construction (controls were gated on licence at collection, the AI arm was not), so it was not a property of AI-assisted repos. A like-for-like sample is in `data/license_base_rate_stats.txt`.

## License

MIT
