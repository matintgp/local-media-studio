# Acceptance and verification

The implementer must provide exact runnable commands and actual results. Below are required gates, not claims that tests already exist.

## CPU/cloud gates

- Fresh dependency install using lockfiles; backend lint/type/test and frontend lint/type/test/build pass. CI never downloads model weights or invokes a real engine.
- Launch mock mode with no engine running or API key. Create a Persian project, generate a labelled mock image, reuse it for video/ambience, generate speech/music, compose and export, refresh and reopen the project.
- Synthetic FFmpeg test produces an actual playable MP4 with expected dimensions/duration and audible tracks. Verify trims, multi-shot ordering, offsets, gains, fades, speech ducking, unequal frame rates/sizes, missing audio and optional subtitles. Probe output metadata rather than asserting only that a subprocess ran.
- Scheduler concurrency tests prove one admitted GPU job across both adapters, external-queue conflict detection, restart recovery, lost submit response, cancellation ownership, idempotent Wan retry and no blind Comfy duplicate. Crash DB/job transition boundaries deliberately.
- Mock HTTP/MCP transport tests cover initialize/session headers, SSE result parsing, structuredContent and isError, async polling, expiry and context recovery, unavailable model and failed job. Mock responses must match checked-in sanitized schema/contracts.
- File/API tests cover path traversal, Windows path/junction cases, cross-origin writes, unauthorized media access, upload limits, disk reserve/staging cleanup and subtitle/filter injection.
- Browser tests cover RTL/LTR, form submission, job progress/reconnect, gallery reuse and composer/export. Capture real screenshots from the running app, not design mockups.
- Runtime works without remote fonts/analytics or mandatory external model provider. Missing FFmpeg disables export with instructions; no auto-download.

## On-device gates for local reviewer

- Inspect PR/dependency lockfiles/scripts before installation. Install app dependencies separately from engine venvs, under approved storage.
- Apply ignored machine configuration. Check existing engines and installed template/model availability without new downloads.
- Render one Z-Image image; upload/reuse it in Wan2.2 FastWan; generate MMAudio, Persian and English OmniVoice and ACE-Step music sequentially. Check saved outputs, provenance and actual metadata. Listen to speech/music and inspect video frames manually.
- Verify model-switch crashes are surfaced as engine disconnected/unknown job, not retried silently. A native Comfy/torch_cpu.dll crash occurred during a FLUX checkpoint load and recovered on cold restart; underlying cause remains unproven. Do not fix it by upgrading engine packages in this PR.
- Confirm storage/caches stay on configured B roots, previous models/backups unchanged, no accidental media duplication, restart recovery and final MP4 audio/video sync.

## PR report

List completed features, tested commands/results, screenshots and explicitly unverified on-device gates. Any missing required adapter or broken export path is an incomplete MVP, not merely a future enhancement. Deliver code in PR; do not merge or claim local deployment happened in cloud.
