# Product requirements — first usable release

## Goal and user

A single-user local creative studio that makes existing media engines approachable without exposing node graphs or raw JSON in the ordinary creation flow. Persian is the default UI language, English is fully usable. Professional output means deliberate project workflows and inspection tools; do not promise artifact-free generation from models.

## Required flows

1. **Project:** create/rename/archive project; persist brief, aspect ratio, language, assets, recipes and history. Archiving changes metadata, not source files. Show recent projects and resume an interrupted project.
2. **Image:** enter prompt, seed, dimensions and preset; submit Z-Image Nunchaku through ComfyUI; preview/save/reuse output as video start image. FLUX is an optional existing fallback, not a required download. Advanced settings are collapsible.
3. **Video:** select imported/generated start image; prompt motion; set dimensions, fps, frame count with duration shown in seconds; run Wan2.2 5B FastWan. Initial preset: 640 square, 121 frames, 24 fps, 3 steps, guidance 1. Offer safe short clips and explain actual media duration after generation. Do not claim a 4K output just by labelling it.
4. **Speech:** Persian or English text, explicit language, seed, 32-step OmniVoice preset, automatic duration. Preview and regenerate a segment. Display that pronunciation should be reviewed. No voice cloning required in this release.
5. **Music:** caption/style and lyrics fields; instrumental toggle inserts [Instrumental]; duration and seed; ACE-Step 1.5 Turbo + 0.6B LM preset, 8 steps. Preview output and reuse it as a composer track. Singing quality is not a guaranteed feature.
6. **Ambience:** choose existing video; prompt/negative prompt/seed; MMAudio job creates a separate video with generated soundtrack. Preserve silent original and expose soundtrack for composition. Do not confuse ambience with narration or lip synchronization.
7. **Gallery:** image/video/audio players; project/modality/date/status filters; provenance, settings, seed and actual metadata; import files; reuse asset in next task; reveal/download references through controlled routes. Missing source files have a visible state. No mandatory bulk copies of existing engine outputs.
8. **Queue:** durable waiting/running/cancel-requested/cancelled/succeeded/failed/unknown states, real progress when available, engine health, reconnect, safe retry and restart recovery. Show load/decode/postprocess stages rather than a fabricated ETA. All GPU work from both engines shares one admission slot. No unbounded batch submission into an external engine queue.
9. **Workflows:** built-in image→video, video→ambience, text→speech, caption→music and final-clip recipes; edit steps/inputs; add optional branches; inspect estimated storage, dependencies and missing inputs before run. A simple ordered/DAG form is sufficient; a full node editor is not required. Completed nodes are reusable; retry only failed nodes without duplicating upstream jobs. Material settings changes invalidate downstream cached steps.
10. **Composer:** select/order existing video shots; set in/out points; add narration, music and ambience tracks; offset, trim, gain, fades and music ducking under speech; optional supplied SRT/VTT subtitles; export MP4. Provide a preview/summary of timing. Reject unsupported transforms explicitly. V1 may use a form-based clip list and track lanes rather than a frame-accurate nonlinear editor.
11. **Settings:** mock/real mode, locale, theme, engine URLs, storage roots, minimum free-space reserve, installed-model availability, optional provider connection status. Connection settings are local and untracked. Missing engine/model/FFmpeg produces an actionable message, no automatic installer.

## Out of scope

Cloud media hosting, multi-user auth/billing, new model manager/downloader, training/LoRA training, lip sync, advanced video editor, mobile application, public server deployment, autonomous shell agent and new chatbot model installation. A provider interface is included for later prompt assistance; no paid account or provider is required now.

## Non-functional requirements

- Works on Windows and CPU-only cloud dev; no dependence on CUDA in the app process.
- UI and job history work while an engine is disconnected. Explicit mock label on every mock job/output and a persistent mode badge.
- Reload/restart preserves projects, workflows and job linkage. Never report lost external jobs as cancelled or completed without evidence.
- Interface works at desktop 1366×768 and narrow/tablet widths without hiding the primary actions.
- Existing model installs, engine settings, source media and environment backups stay intact.
- Maintain an explicit configurable disk reserve; default example is 60 GiB on the data volume, configurable by the owner. Current approved setup budget for models is already almost exhausted: no new model/runtime downloads are authorized by this app task.
