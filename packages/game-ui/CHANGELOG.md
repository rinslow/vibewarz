# @vibewarz/game-ui

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
