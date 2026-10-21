# Verification report — CPU mock sandbox (2026-10-21)

**Status: incomplete MVP; owner GPU checks have not run.** Implementation changes are proposed on a separate feature branch for review; they must not be merged before the remaining acceptance gates pass.

## Checks actually run

- `STUDIO_DATA_ROOT=$(mktemp -d) PYTHONPATH=backend pytest -q backend/tests` — **12 passed in 8.10 s (re-run 2026-10-21)** on Linux with Python/FastAPI/httpx/FFmpeg already available in the sandbox.
- TypeScript syntactic transpile of `frontend/src/main.tsx`, `frontend/vite.config.ts` and `frontend/e2e/workspace.spec.ts` via globally installed TypeScript — **no syntactic diagnostics**, not equivalent to a typecheck or bundle build.
- A real CPU FFmpeg H.264/AAC MP4 was created and probed by backend tests: 2 s single-shot export with narration/music/sidechain ducking; heterogeneous multishot composition, audio-less input, SRT subtitle mux. No GPU, model, model download, or engine modification.

## Not run / not verified

- Fresh npm install and locked frontend build: **not run** because this sandbox has no network access and no cached React/Vite packages. `frontend/package-lock.json` is absent. Required acceptance gate is open.
- Complete transitive backend dependency lock and lint/typecheck: not finished; requirements pin only top-level packages.
- Playwright browser tests and screenshot capture: test source is included at `frontend/e2e/workspace.spec.ts` but has **not run**. No UI screenshots are claimed. The CI workflow attempts screenshot collection after dependency installation.
- Live ComfyUI Z-Image and WanGP MCP job submission, uploads, model discovery, output access or cancellation on owner Windows/GPU: **not run**. Implemented transports require an on-device integration gate.
- Real WanGP media upload tickets and virtual media materialization, reliable external queue introspection, Comfy websocket progress, cancellation of owned running jobs, multi-step workflow DAG dependencies/recovery are **unfinished**. In real mode ambiguous or unsupported operations fail closed. The real video form returns an explicit 409 until authorized upload ticket handling exists.
- Multi-worker scheduler is unsupported (`--workers 1`). The browser screenshot gate remains open. Branch and PR publication are separate from test verification; their availability does not mean the application is production-ready.

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
