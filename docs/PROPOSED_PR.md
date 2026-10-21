# Proposed PR review notes

**Title:** feat: implement CPU mock Local Media Studio and conservative real engine transports
**Base:** main  
**Head:** feat/studio-mvp

## Implemented in source overlay

- React/TypeScript/Vite Persian-first RTL and English LTR creative workspace; projects, modality forms, gallery/import, queue inspection, presets, a structured manual workflow form and clip composer.
- FastAPI/SQLite persistent projects/assets/jobs/events/workflows/exports with transactional single GPU admission and a fail-closed unknown-job state.
- CPU-only labelled synthetic/mock generation; real FFmpeg cut/concat/audio mixing and SRT muxing; strict asset-id and canonical path checks.
- ComfyUI HTTP adapter with validated vetted Z-Image template; WanGP MCP adapter with initialize/session headers, SSE/JSON-RPC result checking, stable request ID and non-replaying ambiguous submissions.
- Linux CPU tests, Windows check/start scripts, CI instructions and README-IMPLEMENTATION.md.

## Checks

See `docs/TEST_REPORT.md`: 12 backend tests pass; no real GPU or browser tests claim. Source-only TypeScript syntactic transpilation passed, but dependency install/build and browser capture not run. GitHub Actions browser test passed (1 Chromium test) and captured four labelled mock screenshots. See [screenshot artifact](https://github.com/matintgp/local-media-studio/actions/runs/39551358401/artifacts/12323941316).

## Blockers and remaining gaps

- This branch intentionally stays separate from main. Do not merge before Windows/GPU review and acceptance checks.
- Dependency lockfiles, real Wan upload/virtual media, engine external activity discovery, authoritative progress, safe owned cancel, workflow dependency outputs and dedicated workspace recovery remain incomplete. CI mock browser screenshots exist; broader coverage remains required.
- Real adapters have mocked transport tests and MUST be reviewed on the owner's Windows GPU before production use. No models or Torch installed/downloaded; Pinokio and original media untouched.

## Integration checklist

Review code and dependency pins; create the exact approved B:/MediaStudio app data root; install app dependencies separately; build Vite; run mock and browser acceptance; configure Comfy/Wan loopback URLs and engine output roots; verify external queue control; test image→video upload, speech, music, ambience sequentially, composing with SRT and engine crash recovery. Keep main unchanged until review.
