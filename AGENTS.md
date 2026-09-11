# Market Event Radar Agent Continuity Protocol

This repository is the canonical producer for the event-data side of the NEGENTROPIC ATARAXIA investment system.

## Before substantive work

1. Verify the current `main` HEAD and recent merged/open PRs.
2. Read `docs/MARKET_EVENT_RADAR_HANDOFF.md`.
3. Read `docs/MARKET_EVENT_RADAR_STATE.json`.
4. Compare `verified_code_commit` with current history. Documentation-only commits after that SHA are acceptable; implementation changes are not. If code moved, reconcile the handoff before changing anything.
5. If the task changes the public snapshot/consumer contract, also inspect `futurenowchen/investment-dashboard` and its handoff before implementation.

Do not reconstruct completed work from chat memory when repository evidence exists.

## Architecture boundaries

- Official-source collection is the stable base layer.
- Consensus is a separate optional provider layer.
- Surprise is computed from official Actual versus eligible pre-release/PIT Consensus.
- Event Reaction is a later, separate market-price layer.
- Consensus credentials/provider failure must never make the official feed unavailable.
- Never substitute a provider's proprietary model forecast for survey consensus.
- Never commit API keys or secrets.

## After substantive work

Update both:

- `docs/MARKET_EVENT_RADAR_HANDOFF.md`
- `docs/MARKET_EVENT_RADAR_STATE.json`

Record completed work, PR/commit/test/CI evidence, blockers, do-not-repeat items, and exactly one executable next action. Keep `verified_code_commit` pointed at the latest implementation commit represented by the handoff; a later docs-only handoff commit may sit above it.
