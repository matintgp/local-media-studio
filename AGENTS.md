# Instructions for implementing Local Media Studio

Read tasks/CHATGPT_TASK.md and every specs/*.md before editing. This repository starts as a specification handoff, not a finished application.

## Scope

- Implement the runnable app, tests and documentation, not another planning-only response.
- Use the proposed lightweight stack unless a concrete compatibility problem is documented in an ADR.
- Preserve the specifications; record justified changes rather than deleting acceptance requirements to make tests pass.
- Work in a feature branch and deliver a PR. Do not merge or deploy to a user's computer.
- No model downloads, Torch installs, engine environment changes, Windows settings changes or engine auto-updates.
- Never embed machine paths, private media, credentials, MCP contexts, session headers or upload tickets in commits.

## Engineering boundaries

- Explicit mock and real modes. Mock output must never be represented as actual model generation.
- One durable, cross-engine GPU admission slot. External engine activity must also block new submission. Unknown/lost job status is not permission to resubmit or release the slot.
- Validate engine responses including tool-level success; an HTTP 200 is insufficient.
- No shell=True, user command execution, arbitrary workflow Python nodes or arbitrary filesystem/URL proxy endpoints.
- Defaults bind to loopback. Validate Host/Origin; reject cross-site writes. Keep provider keys exclusively on the backend.
- Project imports and engine output references must pass canonical-path checks, including Windows junction/symlink escapes.
- Do not delete existing source media. Space estimates and explicit retention controls precede any deletion or large copy.
- Do not add telemetry, analytics, CDN assets, remote fonts or runtime network requirements for the UI.

## Verification and delivery

Document executable check commands as soon as scaffolding exists. Add meaningful scheduler, adapter, file-boundary, media assembly and browser tests. Verify Persian RTL and Latin LTR fields, keyboard flow and offline/disconnected states.

Include lockfiles, a small CPU-only demo, CI, screenshots, migration/setup notes and a truthful test report. Clearly identify checks requiring the owner's Windows/GPU. Do not claim those passed in a cloud sandbox. Disclose unfinished items in the PR rather than hiding buttons or silently using mock adapters.
