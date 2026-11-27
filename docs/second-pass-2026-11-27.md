# Second pass, 27 November 2026: what 46 pairs can and cannot support

Post 1 reported no statistically significant difference on any static metric. The
obvious next question was whether that null says something about vibe-coded code or
only something about the sample. This pass answers that with four checks that can be
re-run from the data in the repo: statistical power, how verifiable the AI arm
actually is, an engineering-hygiene comparison the static metrics skipped, and the
licence base rate the study never measured because the control arm was gated on it.

Short version. The null is real but narrow: at 46 pairs the design can only detect a
large difference. The AI arm is 85% unverifiable by commit evidence. On tests, CI,
type hints and exception handling the two arms are indistinguishable. And the licence
attrition that shaped the first analysis was one-sided by construction, not a
property of AI-assisted repositories.

## 1. Power: the null only rules out large differences

`scripts/power_analysis.py` computes, per metric, the standardised paired effect
`d_z = mean(delta) / sd(delta)` with a bootstrap 95% CI, then simulates the power of
the two-sided Wilcoxon at n=46 over a grid of true effects.

| metric | d_z | 95% CI | Wilcoxon p |
|---|---|---|---|
| pct_cc_gt_10 | -0.243 | [-0.550, +0.041] | 0.102 |
| lizard_avg_nloc | -0.238 | [-0.538, +0.042] | 0.172 |
| lizard_avg_ccn | -0.173 | [-0.487, +0.105] | 0.177 |
| avg_tokens_per_func | -0.162 | [-0.484, +0.127] | 0.304 |
| docstring_viols_per_kloc | -0.159 | [-0.505, +0.127] | 0.177 |
| cc_mean | -0.153 | [-0.453, +0.134] | 0.362 |
| mi_min | -0.133 | [-0.453, +0.161] | 0.275 |
| docstring_density | -0.093 | [-0.304, +0.287] | 0.584 |
| sloc | +0.096 | [-0.368, +0.260] | 0.555 |
| cc_max | +0.051 | [-0.279, +0.289] | 0.772 |
| lizard_max_ccn | +0.066 | [-0.264, +0.305] | 0.942 |
| comment_ratio | +0.005 | [-0.228, +0.475] | 0.124 |
| mi_mean | +0.003 | [-0.322, +0.280] | 0.914 |

At n=46 the minimum detectable effect at 80% power is `|d_z| = 0.44`. Power at 0.3
is 50%, a coin flip. Five metrics (sloc, docstring_density, cc_max, mi_mean,
lizard_max_ccn) have their whole interval inside the undetectable band, so for those
the study cannot separate the arms from identical.

The practical answer: about 95 pairs at 80% power for `d_z = 0.3`, or 55 for 0.4.
The current 46 is enough for a large difference and nothing smaller. That is the
honest scope of the post 1 headline.

Full output: `data/power_analysis.txt`.

## 2. The AI arm is 85% unverifiable

Of the 202 accepted candidates in the AI arm, by strength of evidence:

| evidence | n | share |
|---|---|---|
| bot-contributor commit (claude, Copilot, cursor) | 19 | 9.4% |
| README declaration | 11 | 5.4% |
| query-only (surfaced by a vibe-coding search, no trace in README or commits) | 172 | 85.1% |

The 46 analysed pairs carry the same shape: 9 bot, 5 README, 32 query-only.

This is the uncomfortable part for the whole genre, not just this study. A
search-based sample labelled "vibe-coded" is 85% unverifiable: the label comes from
a query match and nothing else. Two caveats cut in opposite directions, and both
matter. Agents run locally under the developer's own Git identity leave no bot
commit, so absence of a trace is not evidence of absence. And a search match is not
nothing: the term appeared somewhere in the repository, which is why it surfaced.

Descriptively, the bot-evidence subgroup shows a larger negative complexity delta
than query-only repos (median `pct_cc_gt_10` delta -3.9 against -0.4), which is what
you would expect if the label is diluted by false positives. With n=9 and
Mann-Whitney p=0.89 it is a direction to test, not a result.

## 3. Engineering hygiene: no difference either

Static complexity says nothing about whether a repository has tests, CI, pinned
dependencies, type hints or a bare `except:`. `scripts/measure_hygiene.py` measures
those from a shallow clone of all 92 repos, arm-blind, and
`scripts/hygiene_stats.py` joins the arms afterwards. 86 of 92 cloned cleanly; 40
pairs have both sides measured.

Practices, exact McNemar on discordant pairs:

| practice | AI arm | traditional | pairs disagreeing | p |
|---|---|---|---|---|
| has tests | 98% | 92% | 4 | 1.000 (raw 0.625) |
| has CI workflow | 70% | 78% | 11 | 1.000 (raw 0.549) |
| declares dependencies | 78% | 72% | 16 | 1.000 (raw 0.804) |
| pins with a lockfile | 32% | 25% | 13 | 1.000 (raw 0.581) |
| has pyproject.toml | 62% | 62% | 16 | 1.000 |

Rates and coverage, paired Wilcoxon, all q above 0.75 after Benjamini-Hochberg
within the family. The single lead worth a mention: prints per kloc, AI median 2.1
against 3.6 (p=0.084, q=0.76, r=-0.315). A lead, not a result.

Composite hygiene score (tests, CI, packaging, lockfile, out of 4): 2.77 against
2.67, paired p=0.63. Also nothing.

Full output: `data/hygiene_stats.txt`, one row per repo in
`data/hygiene_metrics.csv`.

## 4. The licence gate was one-sided, and the base rate runs the other way

`analyze_repos.py` skipped 73 repositories for licence reasons in the first run, and
every one of them sat in a set where the AI arm could lose repos this way and the
control arm could not: `collect_controls.py` rejected `no-license` at collection
time, while `refilter_candidates.py` accepted unlicensed candidates and deferred the
check to clone time. So the "40 skipped" figure was an artefact of two different
filters, not a finding about AI-assisted repositories.

`scripts/collect_license_base_rate.py` re-collects the traditional arm with the same
structural filters and no licence gate, and
`scripts/license_base_rate_analysis.py` compares the two.

| group | n | no licence | NOASSERTION | recognised OSS licence |
|---|---|---|---|---|
| AI-assisted (vibe queries) | 202 | 61 (30.2%) | 15 (7.4%) | 126 (62.4%) |
| traditional, no gate | 67 | 26 (38.8%) | 1 (1.5%) | 40 (59.7%) |
| the study's own control arm (gated) | 200 | 0 (0.0%) | 26 (13.0%) | 174 (87.0%) |

Unlicensed against licensed, AI arm versus the like-for-like traditional arm: odds
ratio 0.68 (95% CI 0.38 to 1.21), Fisher exact p=0.228. The point estimate says the
traditional repositories are the unlicensed ones, which is the opposite of what the
one-sided gate implied, but the interval is wide enough that the honest reading is
"no evidence either way". The direction is at least consistent: stratified by size
band the odds ratios are 0.60, 0.53 and 0.61, and by the dominant star band 0.79, so
every stratum points the same way while none is individually significant.

Among licensed repositories the mix is unremarkable: 85% permissive in the AI arm
against 82% traditional, copyleft odds ratio 0.84 (p=0.80).

The traditional sweep stopped at 67 accepted candidates rather than the 250 the
script targets, because the run is slow (three API calls per candidate) and this was
a side question. `collect_license_base_rate.py` resumes from the CSV, so the number
in `data/license_base_rate_stats.txt` can be refreshed by re-running it. Treat 67 as
an estimate: the 95% interval on a 38.8% share at that size is roughly 27% to 51%.

The direction matters more than the p-value: the study's own assumption, that
unlicensed repositories are an AI-arm problem, does not survive a like-for-like
sample. Any future run should drop the gate and report licence presence as a
descriptive variable instead.

## What this changes

1. Post 2 should be the methods note, not a second "no difference" post. The finding
   is about resolution and instruments: at 46 pairs you can only see a large effect,
   and 85% of the arm rests on a self-label.
2. The next data step is a registered arm: select on bot evidence only (19 candidates
   today), expand toward 95 pairs, drop the licence gate, and fix the metric list
   before measuring.
3. Post 1's claim stands as written, but its scope should be stated with it: no
   detectable difference at the resolution this sample allows.

## Reproduce

```
.venv/bin/python scripts/power_analysis.py
.venv/bin/python scripts/measure_hygiene.py
.venv/bin/python scripts/hygiene_stats.py
GITHUB_TOKEN=$(gh auth token) LICENCE_TARGET=250 .venv/bin/python scripts/collect_license_base_rate.py
.venv/bin/python scripts/license_base_rate_analysis.py
```

Each script writes its own file under `data/` and prints what it measured. The
hygiene measurement never reads the arm mapping; the join happens in
`hygiene_stats.py`, the same order `analyze_repos.py` and `aggregate_stats.py` use.
