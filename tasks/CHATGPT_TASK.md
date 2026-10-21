# Build Local Media Studio — implementation task

Repository: https://github.com/matintgp/local-media-studio

Implement the first usable release of the local media application specified in this repository. Read AGENTS.md, README.md, specs/PRODUCT.md, specs/ARCHITECTURE.md, specs/INTEGRATIONS.md, specs/SAFETY.md, specs/DESIGN.md, specs/ACCEPTANCE.md and docs/LOCAL_HANDOFF.md first. Use examples/recipes as integration seeds, not as evidence of live access.

The owner already has working ComfyUI and Wan2GP installations on a Windows computer with an RTX 5060 Ti 8 GB and 32 GB RAM. Image, short video, video-conditioned ambience, music, Persian speech and English speech have each produced real outputs. Your cloud environment cannot access that computer or its loopback ports. Do not download models, install GPU packages, replace engines or pretend to run real GPU inference.

Build a polished, Persian-first RTL and English LTR web app with projects, creation forms for each modality, preset management, durable cross-engine queue, asset gallery, reusable multi-step workflows and a final-clip composer. The composer must actually trim/sequence shots, mix narration/music/ambience with gain and speech ducking, optionally add supplied subtitles, and export playable MP4 using FFmpeg. This is an application implementation task, not just a UI mockup or another design document.

Use React/TypeScript/Vite, FastAPI and SQLite, with small locked dependencies. Provide a clearly labelled CPU-only mock mode that exercises complete flows and a real mode with tested ComfyUI HTTP/WebSocket and WanGP Streamable HTTP MCP adapters. Follow exact job recovery and idempotency rules in the specs. Keep heavy jobs sequential across engines. Do not start or stop Pinokio engines automatically; report their status and give a reconnect control.

Design a professional creative workspace: project-oriented navigation, restrained dark theme, strong typography, media preview as the focal point, progressive disclosure of advanced controls, keyboard accessibility, explanatory errors, honest progress, storage visibility, and sensible Persian/English mixed-direction handling. No remote fonts, mandatory API subscription, generic marketing dashboard, fake quality labels or dead controls.

Optional assistant support must have a provider interface for future local/OpenAI-compatible services, but the MVP must work without any LLM/key. A manual structured workflow planner is required now. Do not implement an arbitrary command-running agent. An assistant's future tool actions must go through validated application jobs and the same scheduler.

Work autonomously through implementation and tests. Add CI, meaningful unit/integration/browser coverage, small synthetic media fixtures generated without model weights, reproducible setup commands, a Windows PowerShell run path, screenshots in Persian/English, and an updated README. Separate cloud-verified checks from tests that require the owner's hardware. If a requirement genuinely cannot be finished, document the exact gap and impact; do not silently swap a real adapter for a mock or claim the whole app is production-tested.

Deliver on branch `feat/studio-mvp` (or a uniquely suffixed feature branch if occupied). Open a PR targeting main when the environment permits it; do not merge. If creating a PR is unavailable, leave a committed branch/patch and say exactly how the owner can obtain it. Include a concise change description, commands and test results, screenshots, remaining risks and local verification checklist in the PR. Never publish credentials, private outputs, engine workspaces, session contexts or user-specific filesystem paths. The local assistant will review your PR and handle installation and real GPU validation later.
