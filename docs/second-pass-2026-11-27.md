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

A commit scan is only one instrument, and a second one changes the picture. Agents
also leave files: rule sets, instruction files, MCP configs. Those survive a history
rewrite, and `scripts/detect_ai_artifacts.py` looks for them in the committed tree of
every repo in both arms (194 of the 202 AI-arm candidates answered). Strong artefacts
are `.cursorrules` or `.cursor/`, `.claude/` or `CLAUDE.md`, Copilot instruction
files, `.windsurfrules`, aider config, `.clinerules` or `.roo`, `.continue`,
`.specstory` and MCP configs. `AGENTS.md` or a prompts directory alone counts as weak,
because plenty of hand-written repositories carry those.

| evidence tier | n | strong artefact present |
|---|---|---|
| bot-contributor commit | 19 | 12 (63%) |
| README declaration | 11 | 6 (55%) |
| query-only | 164 scanned | 43 (26%) |

That 26% is the interesting number. A quarter of the repos with no commit or README
trace still ship agent tooling, so the commit scan was under-counting badly. Across
both instruments the arm splits like this:

| evidence | n | share |
|---|---|---|
| commit or README | 30 | 15.5% |
| strong tooling artefact | 61 | 31.4% |
| either instrument | 73 | 37.6% |
| no trace of any kind | 121 | 62.4% |

So the honest figure is 62% without a trace, not 85%, and the 85% quoted from the
commit scan alone was an artefact of using one instrument. What remains is still the
main caveat for the genre: a search-based sample labelled "vibe-coded" is mostly a
label, and section 5 covers what happens when people scrub the traces on purpose.

Descriptively, the bot-evidence subgroup shows a larger negative complexity delta
than query-only repos (median `pct_cc_gt_10` delta -3.9 against -0.4), which is what
you would expect if the label is diluted by false positives. With n=9 and
Mann-Whitney p=0.89 it is a direction to test, not a result.

## 3. Engineering hygiene: no difference either

Static complexity says nothing about whether a repository has tests, CI, pinned
dependencies, type hints or a bare `except:`. `scripts/measure_hygiene.py` measures
those from a shallow clone of all 92 repos, arm-blind, and
`scripts/hygiene_stats.py` joins the arms afterwards. 86 of 92 cloned cleanly; 40
pairs have both sides measured. Of the six that did not: five no longer clone
(deleted, renamed or made private in the three months since collection) and one has
no Python files left in it. That is 6.5% attrition in a sample collected in August,
which is worth knowing for anyone planning to reuse a repository sample after a few
months. Each failure is listed with its status in `data/hygiene_metrics.csv`.

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
| traditional, no gate | 250 | 96 (38.4%) | 14 (5.6%) | 140 (56.0%) |
| the study's own control arm (gated) | 200 | 0 (0.0%) | 26 (13.0%) | 174 (87.0%) |

Unlicensed against licensed, AI arm versus the like-for-like traditional arm: odds
ratio 0.69 (95% CI 0.47 to 1.03), Fisher exact p=0.074. At 250 candidates the interval
nearly excludes 1 without reaching it, and the direction is the opposite of what the
one-sided gate implied: if anything the vibe-coded repositories are the better
licensed ones. The direction is consistent across strata too, with odds ratios of 0.77
and 0.69 in the two usable star bands and 0.50, 0.58 and 0.58 across the size bands
(Mantel-Haenszel pooled 0.77), none individually significant.

Among licensed repositories the mix is unremarkable: 85% permissive in the AI arm
against 83% traditional, copyleft odds ratio 0.84.

The sweep ran to its 250-candidate target (864 candidates examined). Treat 38.4% as a
sample estimate: the 95% interval on that share at n=250 is roughly 32% to 44%, and
the traditional arm comes from generic Python queries rather than a census.

The direction matters more than the p-value: the study's own assumption, that
unlicensed repositories are an AI-arm problem, does not survive a like-for-like
sample. Any future run should drop the gate and report licence presence as a
descriptive variable instead.

## 5. People hide it, and what that does to the null

Some authors scrub traces deliberately: bot co-authorship rewritten, agent rule files
removed, commits squashed. The AI arm is therefore a lower bound on AI-assisted
repositories at every tier, and no instrument available here can see the scrubbed
ones. That belongs in the write-up as a stated limit, not as a footnote.

The larger problem is the other direction. The control arm was collected as "no AI
mention in the README, no bot commit", so a hand-written-looking repo that is really
agent-assisted lands there and dilutes the comparison. The artefact scan measures how
often that happened: **39 of 189 scanned control repos (20.6%) carry a strong AI
tooling artefact**, and a further 16.9% carry a weak one. Under the study's own
definition those are not clean controls.

Two-sided misclassification dilutes a real difference by about `(1 - c - f)`, where
`c` is the contaminated share of the control arm (measured: 20.6%) and `f` is the
hand-written share of the AI arm (not identifiable from this data). So the dilution
is bounded rather than estimated:

| hand-written share of AI arm (f) | measured effect as share of true | true effect multiplier |
|---|---|---|
| 0% | 79% | up to 1.26x |
| 10% | 69% | up to 1.44x |
| 20% | 59% | up to 1.70x |
| 40% | 39% | up to 2.54x |

Put that next to the power numbers. The observed trends sit at `d_z` 0.15 to 0.24, and
the design detects 0.44 at 80% power. Multiply the trends by 1.3 to 1.7 and they land
at 0.19 to 0.41: right at the edge of what 46 pairs could have seen. That is a
coherent explanation for a null that has a consistent direction behind it, and it is
testable: clean the controls, expand the sample, and the direction should either
survive at the edge of detection or collapse to nothing.

The limit of the argument matters. Dilution moves a real difference toward zero and
does nothing to a genuinely null result. It cannot manufacture an effect, so this
explains how a medium difference could hide in this sample without licensing the claim
that one is hiding.

## What this changes

1. Post 2 should be the methods note, not a second "no difference" post. The finding
   is about resolution and instruments: at 46 pairs you can only see a large effect,
   62% of the arm carries no trace at all, and about a fifth of the control arm is
   probably not a control.
2. The next data step is a registered arm: select on bot evidence plus tooling
   artefacts (73 candidates today), expand toward 95 pairs, drop the licence gate,
   and fix the metric list before measuring.
3. Re-collect the control arm through the artefact scan. Controls with `.cursorrules`,
   a `.claude/` directory or an agent instruction file are not controls, and at 20.6%
   they are costing the study most of whatever effect it is chasing.
4. Post 1's claim stands as written, but its scope should be stated with it: no
   detectable difference at the resolution this sample allows, in a comparison that
   dilutes itself.

## Reproduce

```
.venv/bin/python scripts/power_analysis.py
.venv/bin/python scripts/measure_hygiene.py
.venv/bin/python scripts/hygiene_stats.py
.venv/bin/python scripts/detect_ai_artifacts.py
.venv/bin/python scripts/artifact_evidence_stats.py
GITHUB_TOKEN=$(gh auth token) LICENCE_TARGET=250 .venv/bin/python scripts/collect_license_base_rate.py
.venv/bin/python scripts/license_base_rate_analysis.py
```

Each script writes its own file under `data/` and prints what it measured. The
hygiene measurement never reads the arm mapping; the join happens in
`hygiene_stats.py`, the same order `analyze_repos.py` and `aggregate_stats.py` use.
