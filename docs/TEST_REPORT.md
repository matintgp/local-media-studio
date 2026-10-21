# Verification report — CPU mock sandbox (2026-10-21)

**Status: incomplete MVP; owner GPU checks have not run.** Implementation changes are proposed on a separate feature branch for review; they must not be merged before the remaining acceptance gates pass.

## Checks actually run

- `STUDIO_DATA_ROOT=$(mktemp -d) PYTHONPATH=backend pytest -q backend/tests` — **12 passed in 8.10 s (re-run 2026-10-21)** on Linux with Python/FastAPI/httpx/FFmpeg already available in the sandbox.
- TypeScript syntactic transpile of `frontend/src/main.tsx`, `frontend/vite.config.ts` and `frontend/e2e/workspace.spec.ts` via globally installed TypeScript — **no syntactic diagnostics**, not equivalent to a typecheck or bundle build.
- A real CPU FFmpeg H.264/AAC MP4 was created and probed by backend tests: 2 s single-shot export with narration/music/sidechain ducking; heterogeneous multishot composition, audio-less input, SRT subtitle mux. No GPU, model, model download, or engine modification.

## GitHub Actions verification (2026-10-21)

- [CI run 39551358401](https://github.com/matintgp/local-media-studio/actions/runs/39551358401) completed successfully: frontend `npm install`, `npm run typecheck`, `npm run build`; backend `pytest` — **12 passed, 1 warning in 8.10 s**; Playwright Chromium browser test — **1 passed (4.8 s)**.
- Four **actual browser screenshots from the labelled mock application**: `create-fa.png`, `queue-fa.png`, `composer-fa.png`, `composer-en.png`, downloadable as [workflow artifact 12323941316](https://github.com/matintgp/local-media-studio/actions/runs/39551358401/artifacts/12323941316). This does not verify any real model inference.

## Not run / not verified

- Local sandbox npm dependency installation timed out, but fresh frontend dependency install, typecheck and production build **passed in CI**. The required committed `frontend/package-lock.json` is still absent.
- Complete transitive backend dependency lock and lint/typecheck: not finished; requirements pin only top-level packages.
- Browser automation now passed in CI and generated four screenshots, but **extended browser coverage** (keyboard flow, disconnected/unknown recovery and full mock video-to-ambience-to-export click flow) remains incomplete.
- Live ComfyUI Z-Image and WanGP MCP job submission, uploads, model discovery, output access or cancellation on owner Windows/GPU: **not run**. Implemented transports require an on-device integration gate.
- Real WanGP media upload tickets and virtual media materialization, reliable external queue introspection, Comfy websocket progress, cancellation of owned running jobs, multi-step workflow DAG dependencies/recovery are **unfinished**. In real mode ambiguous or unsupported operations fail closed. The real video form returns an explicit 409 until authorized upload ticket handling exists.
- Multi-worker scheduler is unsupported (`--workers 1`). Branch and draft PR publication and green CPU CI are not production or real GPU verification.

## Run verification on owner machine after reviewing changes

```sh
cd frontend
npm install
npm run typecheck
npm run build
npm run test:e2e
cd ..
STUDIO_DATA_ROOT=/path/to/existing/approved/data STUDIO_MODE=mock STUDIO_RESERVE_GIB=0 PYTHONPATH=backend pytest -q backend/tests
```

For browser E2E, keep backend (`8787`) and Vite (`5173`) running separately in mock mode. Test-generated screenshots are written under `docs/screenshots/`. On Windows follow `README-IMPLEMENTATION.md` and `scripts/check-windows.ps1` without touching existing engine environments. Do **not** merge this into main without resolving the acceptance gaps.
# Historical cloud report

The original report below is superseded for local verification by [LOCAL_REVIEW.md](LOCAL_REVIEW.md).
