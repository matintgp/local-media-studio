# Local Media Studio — CPU MVP implementation

The existing README and specifications remain intact. The application lives in `backend/studio` (FastAPI and SQLite) and `frontend` (React/TypeScript/Vite). It has a clearly labelled **MOCK / DEMO** CPU-only mode. **Real GPU outputs have not been verified** in the cloud. No engines, model weights, CUDA, Torch or new runtime are installed or downloaded.

## Linux/CPU smoke test (no models)

```sh
cd frontend && npm install && npm run build && cd ..
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
mkdir -p /tmp/media-studio-demo
STUDIO_DATA_ROOT=/tmp/media-studio-demo STUDIO_MODE=mock STUDIO_RESERVE_GIB=0 PYTHONPATH=backend python -m uvicorn studio.app:app --host 127.0.0.1 --port 8787 --workers 1
# open http://127.0.0.1:8787
STUDIO_DATA_ROOT=/tmp/media-studio-tests PYTHONPATH=backend pytest -q backend/tests
```

FFmpeg/ffprobe are required for synthetic video/audio and MP4 export; install only the operating system's lightweight FFmpeg binary through your normal reviewed package manager. The app **never** installs or launches it. All sample media are generated locally from FFmpeg synthetic sources and are labelled DEMO.

## Windows / PowerShell on approved B-drive

Run `scripts/check-windows.ps1` first. Do not change Pinokio engines. Review/approve the data root `B:\MediaStudio` and create it independently if not present; the app refuses to fall back to C:. Use Python 3.11 and Node 22 in a dedicated application environment. From repository root:

```powershell
$env:npm_config_cache = 'B:\MediaStudio\npm-cache'
cd frontend
npm install
npm run typecheck
npm run build
cd ..
py -3.11 -m venv B:\MediaStudio\studio-venv
& 'B:\MediaStudio\studio-venv\Scripts\python.exe' -m pip install -r backend\requirements.txt
.\scripts\run-windows.ps1 -Mode mock -DataRoot 'B:\MediaStudio'
# After review, real mode (no engine changes):
.\scripts\run-windows.ps1 -Mode real -DataRoot 'B:\MediaStudio'
```

Set `STUDIO_COMFY_URL`, `STUDIO_WAN_URL`, `STUDIO_COMFY_OUTPUT_ROOT`, `STUDIO_FFMPEG`, `STUDIO_FFPROBE`, `STUDIO_RESERVE_GIB` in the process environment for site-specific reviewed paths. Default endpoints are loopback 8188 and 7866/mcp. Only run one backend worker. Database `B:\MediaStudio\studio.sqlite3` is automatically migrated to schema v1. Stop the app and copy the DB before upgrades. Rollback stops this app, restores its database from backup and removes only app-owned files if explicitly desired; never delete engine source assets or models.

## Behavior / limitations (verify before GPU use)

- SQLite persists projects, media references, jobs, immutable request IDs/payload hashes, output provenance, workflows, exports and event cursor. One transactional GPU admission slot; unknown external state blocks dispatch and never triggers blind resubmission.
- ComfyUI uses vetted Z-Image API graph, `/object_info` model validation, `/queue`, `/history`, `/prompt`. WanGP uses Streamable HTTP MCP initialize, session headers, JSON/SSE decoding, tools and job polling. **These are transport implementations requiring live protocol verification**; missing availability or uncertain activity blocks generation. No mock fallback in real mode.
- Security: loopback host/origin checks, ID-based local media, read-root containment and path canonicalization, bounded imports/disk reserve, no shell execution, no remote fonts/telemetry. Single-user local app; do not expose it publicly.
- Composer renders actual normalized video clips with CPU FFmpeg H.264/AAC, trims, sequences, music/narration lanes with offsets, gain, fades and sidechain ducking, and probes export. SRT subtitle muxing is experimental; VTT is rejected explicitly.

### Known incomplete integration gates

WanGP external queue discovery and upload-ticket flow need owner-machine schema validation; Comfy output references require configured output root. Virtual `@outputs` Wan media need authorized download/materialization before playing in the gallery or using the local composer. Comfy WebSocket progress and safe owned-running cancellation are not implemented (polling only); unknown status is fail-closed. Cross-process scheduler ownership currently requires `--workers 1` (no process-level leader election). Multi-step workflow execution queues typed steps but does not yet bind outputs/dependency DAG or resume partially successful steps. Composer UI provides shot order and audio offsets but full source trims are API-only. These are **MVP gaps**, not confirmed working features. Reconciliation may require manual review. No hardware test has been run.
