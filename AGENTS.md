# Vibe-Coded vs Traditional Code Quality Study

Empirical study comparing static-analysis quality metrics of self-declared AI-assisted
("vibe-coded") public GitHub repos vs matched traditionally-written repos.

## Decisions & Reasoning
- 2026-08-23: Started as LinkedIn content engine → blog series → preprint (Zenodo DOI).
- Scope discipline: Python-only first (best static analysis tooling).
- Parked future endeavor: survey on AI tool adoption among Malaysian SWE students.

## Feasibility Probe (2026-08-23)
GitHub Search API, unauthenticated (10 req/min limit):

| Query | Total hits |
|---|---|
| `vibe-coding language:python` | 7,520 |
| `vibe-coded language:python` | 5,622 |
| `ai-generated language:python` | 49,683 |

**Verdict: FEASIBLE** — plenty of raw candidates for a ~50-repo AI-assisted arm.

### Caveats found
- Many hits are NOT apps: templates, resource lists, course materials
  (e.g. fastcampus course repo, agent-skills collections). Need filtering:
  - must contain runnable Python source (e.g. ≥N .py files, has main/entry point)
  - exclude repos that are just prompt/config collections (.md/.yaml heavy)
- `ai-generated` query is noisy (content-detection studies etc.) — prefer
  vibe-coding/vibe-coded topics + README declarations ("built with Cursor/Claude/Copilot").
- Quoted queries need URL encoding (`%22`) — raw quotes broke one request.
- Unauthenticated API = 60 core / 10 search requests/min; use tokens or throttle
  during full collection.

## Next Steps (updated 2026-08-24)
1. ~~Control top-up~~ DONE (2026-08-24): data/controls.csv now has 200 accepted
   clean controls — 80× 2024, 40× 2025, 80× 2026 (was 80 all-2026).
   collect_controls.py gained `--years` filter; gh_json got a 30s urlopen
   timeout (a dead TLS socket previously hung the run indefinitely).
2. **Stratified matching:** pair each final AI repo with a control from same
   (LOC band × creation year × star band) stratum, seeded RNG — per
   docs/control-group-criteria.md.
3. **Analysis pipeline:** clone → radon/lizard/pydocstyle/pydocstyle → metrics CSV.
   License check enforced at clone time. Arm-blind until aggregation.
4. AI-arm pool: data/candidates_v2.csv (202 accepted; prioritize 29
   bot-contributor + 11 readme-declaration repos).
5. LinkedIn post #1: kickoff/methodology post once pilot results land.
