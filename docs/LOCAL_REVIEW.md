# Local review and Windows verification

Date: 2026-10-21. Review of PR #1 followed by local corrections; main remains unmerged. Original cloud checks remain in TEST_REPORT.md.

## Findings corrected

- Windows secure_path rejected ordinary native paths. It now accepts valid drive paths while rejecting traversal, alternate streams, UNC/device paths and junction escapes. A Windows junction regression test passes.
- Real engine outputs were unresolved references. Approved native output paths now support preview, reuse/upload and composition without bulk copying originals. MCP session context remains backend-only.
- WanGP adapter guessed list_jobs/availability actions and passed app-only kind into native validation. It now uses supported global list_queue, defaults and preflight. Uploads use same-origin bounded scoped tickets. Real calls verified these fixes.
- Workflow steps now bind earlier image/video outputs instead of queueing independent jobs. Job/link insertion is atomic and successful steps are reused on retry.
- Added an OS worker lock, conservative admission/recovery, owned cancellation, explicit operator abandonment for unknown outcomes, and idle Comfy cache release before Wan generation after checking both queues.
- Added asynchronous serialized export, constrained FFmpeg protocols, disk checks during rendering, SRT/VTT subtitles, non-boosting peak limiting, lockfiles, isolated Windows scripts, project-scoped composer drafts, export status and safe video presets. Removed unused frontend dependency. Optional provider interface requires no API key or model.

## Actual local checks

- App runtime: separate Python 3.12 environment and Node 24. Engine environments unchanged.
- Backend: **18 tests passed**, one upstream Starlette/AnyIO deprecation warning. Covers transport, Windows/junction paths, worker exclusion, dependency binding, source preservation, heterogeneous shots and subtitles.
- Frontend: TypeScript/Vite production build passed.
- Browser: **1 full E2E test passed** using installed Edge and a separate CPU mock server. Includes Persian project, mock image→video, music, an actual composed MP4, gallery and English switch. docs/screenshots contains synthetic mock screenshots only.
- The same application commit also passed GitHub Actions backend, frontend and browser jobs: [CI run](https://github.com/matintgp/local-media-studio/actions/runs/39555083135). Browser reload verified saved composer drafts; a fresh real UI navigation showed zero browser console errors.
- Real application: Z-Image Nunchaku 1024px image → ticket upload → Wan2.2 FastWan 640×640/121 frames/24fps → MMAudio; OmniVoice Persian **3.86s**, English **4.66s**; ACE-Step music **16s**. All six modalities succeeded through the app. The dependent workflow completed.
- A native image output was recovered after a queue/history timing race; scheduler recovery now continues polling known external IDs rather than remaining stuck.
- Final real composition used two repeated 2.5s sections, narration, music, ambience, ducking/fades and supplied Persian subtitles. Probe confirmed **5.000s, 640×640, H.264, AAC 48kHz and mov_text subtitles**. This is a technical demo; late source video frames had artifacts, so earlier frames were used.
- A local Pinokio entry was added and tested with the existing app environment and captured UI URL. No model downloads or engine environment changes. Private outputs/paths/sessions are not published.

## Remaining limits

Usable first local version; not every product aspiration is complete. Composer is a form with previews, not a frame-accurate mixed live timeline. Workflows are ordered with earlier-step bindings, not a general graphical DAG editor. Chat/provider connection, automatic subtitles and lip sync are deferred. Some technical labels remain English. Native crashes and generated media/pronunciation quality need human review. Cloud tests cannot certify these.

Keep the PR separate for owner evaluation. Preserve loopback-only operation and the owner's stricter storage reserve. Free disk is not permission for new model downloads.
