# Visual revision

Owner requested a substantial visual improvement after the first usable app.

- Rebuilt the theme with neutral charcoal/amber tokens, stronger text contrast, a stationary navigation rail, consistent SVG icons and bundled Persian typography.
- Rebalanced creation around a large media viewing stage and compact inspector. Selected real outputs support download/reuse and a recent-output strip.
- Added library search/modality filters, source metadata, clear audio/subtitle artwork and improved empty states.
- Refined the timeline with actual source thumbnails and collapsed editing guidance. The side preview now shows the last composed export rather than duplicating an input shot.
- Simplified Persian labels and added assistant starter prompts that fill the input without making a network call.
- No runtime dependencies, backend changes, model downloads or engine modifications. Bundled font payload is approximately 109 KiB with its OFL license.

Validation: TypeScript/Vite production build and the installed-Edge full demo E2E passed. Browser checks exercise library filtering/search, timeline edits, actual MP4 export, draft reload, assistant planning and horizontal overflow across all seven sections at 390px and 1366px. Persian/English desktop and Persian mobile screenshots are generated from labelled synthetic mock mode. Actual local media was inspected separately; private screenshots/media are not committed.

## Font attribution

[Vazirmatn project](https://github.com/rastikerdar/vazirmatn), version 33.003.
The font and SIL Open Font License are included in frontend/public/fonts.

The previous GitHub Chromium run failed at the timeline playback assertion. CI now uses branded Chrome for the H.264/AAC playback path; local Windows checks use installed Edge. Transient AbortError during clip changes no longer stops the next clip, while actual preview failures display an actionable message. Browser/codec support follows [Playwright browser guidance](https://playwright.dev/docs/browsers#when-to-use-google-chrome--microsoft-edge-and-when-not-to).
