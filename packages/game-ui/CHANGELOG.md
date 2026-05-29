# @vibewarz/game-ui

## 0.2.0

### Minor Changes

- 496273c: game-ui: identify the local player ("YOU") by consistent seat color instead of
  a separate marker. `BlastReplay` and `CurveReplay` now accept an optional
  `mySeat` prop — when set, the viewer's seat row (and the Blast HUD card) is
  tinted with that seat's color so "this is me" reads from color alone. Removes
  the faint Blast "this is you" halo and the muted lowercase "you" HUD label in
  favor of pure color matching. Spectator views (`mySeat` omitted / null) render
  unchanged.

## 0.1.0

### Minor Changes

- d294341: Initial release of `@vibewarz/game-ui` — React components for rendering
  vibewarz games. Includes replay viewers for all three games (`CurveReplay`,
  `BlastReplay`, `PokerReplay`) plus the shared presentational boards
  (`BlastBoard`, `PokerBoard`, `Card`, `ChipStack`, …) used by both replays and
  the platform's live-play UI. Extracted from the closed-source `apps/web` so the
  OSS Python CLI's `vibewarz replay --watch`, the platform replay pages, and the
  platform live-play pages all render through one source of truth. API is
  unstable in 0.x; expect breaking changes between minor versions until 1.0.
