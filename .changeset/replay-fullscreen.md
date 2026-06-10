---
"@vibewarz/game-ui": minor
---

replay: fullscreen mode that respects the chosen aspect ratio. A ⛶ button in the shared playback controls (or the `f` key) fullscreens the replay root — frame plus controls, so the scrubber, speed, and ratio selector stay usable. The frame meet-fits the screen at the selected aspect ratio (16:9 edge-to-edge on typical monitors, 9:16 pillarboxed center, 1:1 between), re-fitting live if the ratio is switched while fullscreen. All four game replays get it via `PlaybackControls`.
