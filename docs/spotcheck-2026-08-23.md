# Spot-Check Results: 2026-08-23

Random sample of 20 passed candidates (seed 42). Judged on: is it a real
application, is it plausibly AI-built, license status.

| Repo | Verdict | Notes |
|---|---|---|
| YCLiuge/Stock_Trading_Analyser | ✅ | "a little practice of vibe coding", app, GPL-3.0 |
| Lilchris007/AGENTS.md_generator | ❌ | Tool FOR vibe coders, not built-by-vibe |
| mrelvisnow/ChoreBoard | ⚠️ | Real app; AI provenance unverified (3 contributors) |
| kevin-earl-denny/vibe-code-boilerplate | ❌ | Boilerplate/template, no license |
| ga1ien/claude-cache | ⚠️ | Claude Code tooling; superseded/abandoned |
| filthyrake/vlog | ✅ | Real self-hosted app; **Copilot listed as contributor**, a strong signal |
| slungus57/Kestrel | ⚠️ | Real tool, but AI provenance unclear |
| rusin-dev/Rp-plus-plus | ⚠️ | "Your Programming Copilot" = AI-assistant tool, not vibe-built |
| tertiarycourses/TGS-...Vibe-Coding | ❌ | Course materials (slipped through: has enough py files) |
| fonscutup654/ELAI-DevKit | ❌ | DevKit/tool for AI dev, not an app built by vibe |
| arbitrary-mooncake/A-Share-...LLM | ✅ | "vibe coding project" per own description, GPL? NOASSERTION |
| BerguzarMuhendis/KatipCelebi | ⚠️ | Real PyQt6 app; no explicit AI evidence in metadata |
| genehand/ha-apps | ⚠️ | "Vibe coded HA apps" desc = good signal; no license though |
| Coolver/home-assistant-vibecode-agent | ❌ | Tool to LET others vibe-code (agent), not itself the artifact |
| ZhenMoon/n.e.k.o_plugin... | ⚠️ | Mentions vibe-coding; plugin w/ OCR etc.; empty contributors list odd |
| keaizuizui/CodeRef-AI | ❌ | Governance platform FOR vibe projects |
| moaju0/Vibe-Prolog | ✅✅ | **`claude` listed as contributor**, the strongest possible confirmation |
| jkblank/VCpod | ✅ | "Vibe-Coded iPod library mgmt": declared by name/desc, MIT |
| devanshutak25/blenderKey | ✅ | declared-ai README, real Blender addon, GPL-3.0 |
| anCode1143/dsa-diary | ❌❌ | Explicitly claims NO LLMs ("not just a vibe coder"), control candidate! |

## Score
- ✅ genuine: 6/20 → but several ⚠️ are plausible with deeper commit inspection
- ❌ misclassified: 7/20
- ⚠️ uncertain: 7/20

**Precision of automated filter ≈ 30% strict / ~50% lenient.**

## Key learnings
1. **Biggest contamination class:** tools *for* vibe-coders mistaken for
   artifacts *of* vibe-coding (AGENTS generators, MCP agents, governance
   platforms, devkits). Fix: description regex excluding
   "(for|tool|platform|kit|agent|boilerplate|template)" near vibe terms.
2. **Bot contributor check works:** `claude` in Vibe-Prolog contributors,
   `Copilot` in vlog. This was the signal we predicted.
3. **anCode1143/dsa-diary is a gift:** explicitly anti-AI repo surfaced by our
   query. It proves control-arm sourcing needs its own query path, and suggests
   searching for such repos deliberately ("no LLMs", "hand-written").
4. Course-material repos still leak through → add "course/tutorial" name check.

## Decisions
- Tighten filter: exclude repos whose *purpose* is AI tooling vs those *built* via AI.
- License required at clone time (already policy).
- Manual curation layer stays: 218 → expect ~60-90 after cleanup, enough for n=50.
