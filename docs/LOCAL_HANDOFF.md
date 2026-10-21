# Local installation and review handoff

This is a deployment plan, not an executable installer. The implementer must add concrete commands after choosing locked package versions. Do not modify existing Pinokio launchers from the cloud task.

## Reviewer procedure

1. Receive PR URL/branch from the owner. Fetch and review diff, runtime dependencies, scripts, CI and test report; keep user changes intact.
2. Run cloud/CPU checks in a separate checkout. Resolve review findings before connecting live engines.
3. Prepare a small isolated app environment and UI build on the selected B-drive location. Ask for a new storage decision if installs exceed the existing authorized cap; do not treat large free space as download permission.
4. Discover current engine URLs through Pinokio rather than assuming the historical UI port. Comfy commonly uses loopback8188; WanGP MCP is configured on loopback7866. The WanGP web UI port can change.
5. Create ignored local settings with existing engine output roots and data root, reviewed model/template choices and disk reserve. Never commit these settings or active MCP contexts.
6. Run real smoke checks one at a time, then test composition, reconnection and restarting the app. Preserve raw engine outputs and legacy backups.
7. Add a Pinokio launcher only as a separate reviewed local change, following the installed Pinokio instructions/examples. Leave engines isolated. Document start/stop, data location, dependency storage footprint and rollback.

## Required implementation deliverables

Windows PowerShell start/check scripts with robust quoting and clear errors; a CPU demo path usable on Linux; application-specific lockfiles; documented ports/storage/config schema; graceful shutdown; versioned SQLite migrations with backup guidance. No administrative privileges, registry/pagefile edits or engine package upgrades.

Rollback stops the new app and restores its own config/database if needed. It must not require reinstalling ComfyUI or WanGP. No deployment task is complete until real engine tests pass and the owner can open the app locally.
