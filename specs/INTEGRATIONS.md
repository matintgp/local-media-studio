# Existing engine integration contract

These notes describe the installation observed when preparing this handoff. They are not a substitute for runtime capability discovery. Cloud implementers must use mocked transports and report live integration as unverified.

## Shared adapter requirements

Provide health, capabilities/availability, validate, submit, get_status, get_result, cancellation capability, reconnect and ownership-aware reconciliation. Return typed states and outputs. Do not scrape Gradio HTML or launch engine Python. A health check must establish actual reachability, not just a running Pinokio launcher flag. Distinguish missing model, engine offline, invalid inputs, unknown job, runtime failure and unsupported action.

Engines stay externally managed by Pinokio. The web app reports start/reconnect instructions; it does not reinstall, update, kill or restart engines automatically. Backend calls engine transports; the frontend only calls the studio backend.

## ComfyUI

- HTTP base URL is configurable; common default http://127.0.0.1:8188.
- GET /system_stats, GET /object_info (or class-specific object info), GET /queue and GET /history/{prompt_id} establish availability, installed node contracts and job state.
- POST /prompt accepts {"prompt": <API node graph>, "client_id": <app correlation id>, "extra_data": <correlation metadata>}. Store returned prompt_id. Treat node_errors as validation failures.
- WebSocket /ws?clientId=... provides events; inspect event types before normalizing progress, with history/queue polling fallback. Disconnect does not mean failed/cancelled inference.
- Outputs use the server history images/files references; media can be retrieved with GET /view?filename=...&subfolder=...&type=output when supported. Resolve only authorized output references, never a user-supplied arbitrary URL. An image may be displayed from a streamed reference without copying the original checkpoint/output tree.
- POST /upload/image accepts multipart input media and returns a server reference. Confirm the installed server's expected fields and wire the reference into a vetted template. Server workflow JSON and UI workflow JSON are different formats.
- Cancellation: distinguish queue removal from /interrupt of the running task. Inspect installed routes and queue ownership before using either. Never clear another user's engine queue.
- The example Z-Image API graph uses NunchakuZImageDiTLoader, CLIPLoader with type lumina2, ModelSamplingAuraFlow shift3, EmptySD3LatentImage, KSampler 9steps/cfg1/res_multistep/simple, VAEDecode and SaveImage. Validate all model basenames/node inputs against object_info before dispatch. No custom-node or model downloads.
- Current engine runs with --disable-dynamic-vram for Nunchaku compatibility. Leave this launcher configuration alone. A native access violation occurred while switching to a legacy FLUX checkpoint; a cold FLUX render later succeeded. The app must surface process loss and ambiguous job outcome; no automatic retry or invented OOM diagnosis.

The sanitized graph in examples/recipes/z-image-comfy-api.json has no machine paths. A recipe editor maps user fields into allowed graph inputs, not arbitrary node code. Do not forward arbitrary uploaded graph JSON to execution.

## WanGP Streamable HTTP MCP

Current installed source commit at handoff: fdc63bdf89358fb13c93cf6b38693fd89a859f00, upstream https://github.com/deepbeepmeep/Wan2GP. Engine packages and source remain separate from the app. Installed launch enables shared UI MCP on http://127.0.0.1:7866/mcp, with profile5/SDPA and INT8 model loading. Never assume the changing Gradio UI port is the MCP endpoint.

Use a supported MCP client implementation; lock its version. Implement initialize plus initialized notification, protocol negotiation, Mcp-Session-Id propagation and Accept application/json,text/event-stream. Parse both JSON and SSE-wrapped JSON-RPC results. Check protocol errors, isError and structuredContent; an HTTP200 alone proves nothing. Reinitialize an expired session (often404) but re-establish workspace context before job calls. Never replay a non-idempotent submit merely because a transport request timed out.

Read tools/list and resources as available. The sanitized tool list snapshot is examples/contracts/wan-tools.json. For progressive-discovery actions, omit arguments to read the contract; use action + arguments object to execute. Unknown action names or settings must not be guessed.

### Context and generation

1. tools/call wangp_workspace with action=current obtains agent_context/workspace. Keep contexts/session headers only in ignored runtime state. Reconcile stored workspace/job references after reconnection; don't replace an owned workspace and assume previous jobs vanished.
2. wangp_model with model_type and action=defaults / capabilities / availability reads native settings and installed status. Discover unsupported actions rather than assuming schemas.
3. wangp_validate takes settings and agent_context. Require valid=true and show diagnostics. Availability doesn't prove ancillary dependencies or inference will succeed.
4. wangp_generate takes settings, agent_context, wait=false and a stable request_id. The installed shared MCP accepted asynchronous submission. If a different server configuration rejects async controls, report the capability mismatch before treating anything as submitted; support bounded waits with a job ID without duplicate submission.
5. Poll wangp_session action=get_job with nested arguments {job_id,wait_s:30,event_limit:3}; stream progress to the app. Require done plus result.success and no task errors. Resolve final gallery_items media_id/path and actual metadata. Native path references such as @outputs are not direct OS/browser paths.

Example envelope:

```json
{
  "name": "wangp_generate",
  "arguments": {
    "agent_context": "<runtime context>",
    "settings": {"model_type":"omnivoice", "prompt":"Hello.", "model_mode":"english", "num_inference_steps":32},
    "wait": false,
    "request_id": "<persisted app job UUID>"
  }
}
```

Same request_id with identical payload is the retry key; changed payload requires a new deliberate job. Payload hash and identifiers are persisted before dispatch. A failed external job is not a protocol error and must be handled explicitly.

### Uploads, postprocessing and media

- To use a Comfy/generated/imported image, discover wangp_session create_file_upload. Follow the returned upload ticket/HTTP PUT contract, limits and allowed origin; then use its virtual reference in the same context. Never reuse the handoff machine's old @documents reference or hardcode active workspace IDs. Ticket destinations must not become an arbitrary outbound proxy. Inspect the installed contract for chunked vs single PUT and completion steps.
- wangp_postprocess with media="video" and no action lists treatments. action="mmaudio" with arguments omitted reads its contract. Execute with concrete media ID, action=mmaudio, arguments={prompt,negative_prompt,seed}, agent_context, wait=false and persisted request_id. A separate job yields a new video; preserve original.
- wangp_toolbox supports extract_audio, extract_video, inspect_audio, remux_media, media_settings, view_media and transcribe_media, subject to installed contracts. Discover before execution. Some toolbox actions return image content blocks rather than just structuredContent.
- inspect_audio is CPU analysis. Whisper transcription, MMAudio and other GPU postprocessors must participate in global GPU admission. Do not treat all postprocessing as GPU-free.
- remux_media can mix audio_ids with optional video_id, gains/fades/offsets/trims/ducking and normalize_lufs, according to its contract. The studio composer can use its own FFmpeg for deterministic assembly across engines rather than requiring Wan-only media IDs for every track.
- Do not expose raw /mcp, session IDs, absolute private paths or all engine tools directly to an untrusted browser or future agent. Build a narrow backend adapter.

### Installed recipe baselines

| Purpose | model_type | Baseline |
|---|---|---|
| Persian/English speech | omnivoice | model_mode persian/english,32steps,auto duration |
| Music | ace_step_v1_5_turbo_lm_0_6b | 8steps,24seconds,[Instrumental] + alt_prompt caption |
| Image to video | ti2v_2_2_fastwan | image_prompt_type S,640x640,121frames,force_fps24,3steps,cfg1,flow_shift3 |
| Soundtrack | postprocess action mmaudio | prompt,negative_prompt,seed |

OmniVoice INT8 URL and Persian/English language choices are already configured on the owner's engine. FastWan accelerator is already present. Missing availability must produce a message, not a download. Examples are minimal overlays: merge over native defaults, apply only validated supported keys, and record the final resolved settings.

## FFmpeg final composer

Discover configured executable/ffprobe safely; no bundled binary auto-download. Implement trimming/sequencing and normalize heterogeneous inputs explicitly. For video exports, map the actual mixed audio stream and encode a broadly playable MP4 (H.264/AAC with CPU fallback). Set deliberate export duration: video timing wins, and shorter audio is padded/longer audio trimmed as specified. Never use -shortest blindly to truncate the picture to a short narration track.

Validate finite numeric timings/gains and ensure in<out. Resample/mix layouts deliberately, avoid clipping, apply gain/fades and sidechain ducking under narration. Support user-supplied subtitles as optional validated assets; do not add a GPU transcription dependency to the app. Stage to an app-owned path, probe the result, and atomically publish the final file. Preserve all sources if interrupted.

## References

- ComfyUI source/protocol routes: https://github.com/Comfy-Org/ComfyUI (server.py, execution.py, API examples).
- WanGP source and docs/API.md: https://github.com/deepbeepmeep/Wan2GP/tree/fdc63bdf89358fb13c93cf6b38693fd89a859f00
- Captured schemas are a compatibility fixture, not a substitute for current engine tool discovery.
