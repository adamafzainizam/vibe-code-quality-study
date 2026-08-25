# Control Group: Matching Criteria

## Goal
Select traditionally-written Python repos that are comparable to the AI-assisted arm,
so observed metric differences are attributable to the development method, not to
confounders (repo type, size, age, popularity, author skill).

## Confounders to control
| Confounder | Why it matters | How we control |
|---|---|---|
| Language | Complexity metrics aren't cross-language comparable | Python only (both arms) |
| Repo purpose | Apps vs libraries vs tutorials have different quality norms | Restrict both arms to **applications** (has entry point/CLI/UI), exclude libraries & tutorials |
| Size | Bigger repos naturally have more duplication/complexity | Match on source LOC bands (see below) |
| Age | Conventions/quality drift over time; AI repos are all 2025+ | Match on creation year: control repos from **2024–2026** |
| Popularity | Stars correlate with polish | Match on star band (0–5, 6–50, 51–500) |
| Solo vs team | Team code differs structurally | Prefer solo-authored repos both arms (≤2 contributors) |
| Activity | Abandoned vs maintained | Both arms: pushed at least once after creation month |

## Matching procedure
1. **Strata:** define strata by (LOC band × creation year × star band).
   - LOC bands: <1k, 1k–5k, 5k–20k, >20k (source .py LOC, computed after clone)
2. For each AI-assisted repo in the final sample, sample **1 control** from the same
   stratum at random (seeded RNG, recorded for reproducibility).
3. If a stratum is empty for controls, drop that AI repo (report attrition).

## Control-arm sourcing
- GitHub search: `language:python created:2024-01-01..2026-08-01` with **negative**
  AI signals: exclude repos whose README matches the AI-declaration regex used in
  `collect_candidates.py`, and exclude topics: vibe-coding, ai-generated.
- Sample from mid/low-star range to mirror the AI arm's profile (most vibe repos
  have <50 stars).
- Exclude: forks, tutorials (name/description containing "tutorial", "course",
  "exercise", "bootcamp"), and repos by authors present in the AI arm.

## Blinding / honesty notes
- Static analysis is automated, so analyst blinding isn't strictly required, but
  the analysis script must NOT know the arm label until the aggregation step.
- Record every exclusion decision with a reason in the CSV (audit trail).

## Sample size (initial)
- 50 AI-assisted + 50 matched controls (pilot: 10 + 10).
- Power note: with n=50/arm we can detect ~0.55 SD differences at 80% power
  (two-sample t-test, α=0.05), adequate for pilot claims, framed as exploratory.

## Provenance signals
- **Commit/contributor bot signatures** (`claude[bot]`, `cursor`, `codex`,
  `copilot`, `devin` etc. appearing as commit authors or contributors) are
  treated as *strong positive evidence* of AI-assisted development.
- **One-directional signal:** their absence proves nothing; many vibe-coders
  strip bot attribution from history. Never use absence as evidence of
  traditional authorship.
- For controls: ANY bot contributor = automatic disqualification.

## Open questions
- [x] Controls: exclude any repo that *mentions* AI tools anywhere in README,
      not just declarations (strict anti-contamination; decided 2026-08-23).
- [x] Licensing: clone only repos with a recognized OSS license (MIT/Apache-2.0/
      GPL/BSD...), same rule both arms (decided 2026-08-23). Preprint publishes
      aggregate statistics only, never source.
