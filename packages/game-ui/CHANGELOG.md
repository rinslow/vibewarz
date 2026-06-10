# @vibewarz/game-ui

## 0.7.0

### Minor Changes

- 47496f4: vibelords: melee strike-accent VFX for all 8 pike/cavalry units. Each body's attack motion gains a signature accent phase-locked to its weapon keyframe (same animation duration, flashing in the window where the strike lands): Clubman swoosh crescent + impact burst, Pikeman thrust flash at the leveled tip, Trench Guard & Dragoon muzzle flash + smoke, Juggernaut energy discharge off the lance orb, Wolf Rider & Knight tip burst + speed lines, Hover Striker bright beam core + ground flare. Pure renderer change — no engine fx involved, so the accents appear on existing replays too. Asset-sheet unit cells get a wider/taller viewBox so right-facing attack accents aren't clipped.

## 0.6.2

### Patch Changes

- 2f48e69: replay: move the vibewarz mark to the left and add the brand icon. Both wordmarks (the in-frame board corner and the playback-controls bar) now sit on the LEFT instead of the right, each prefixed with the vibewarz icon — a green rounded bar rendered as a CSS `::before` on `.vw-replay__wordmark` (pure shape, themeable via `--vw-color-accent`, no asset). The board-corner mark groups with the winner badge (`▍vibewarz 🏆 name`); in the tall 9:16 frame it's lifted off the bottom edge so it stays noticeable.

## 0.6.1

### Patch Changes

- 1b5c385: blast: fix the live play board, which regressed when the replay aspect-ratio work made `BlastBoard` always pad itself to a square with a large meet-fit intrinsic size. That is correct inside the replay's fixed-ratio frame, but the play page renders the board directly into a flexible column, so it ballooned to the full column width, fell out of line with the side panels, and ran past the fold.

  The square padding / large-intrinsic / meet-fit behaviour is now gated behind a new `frame` prop (which only `BlastReplay` sets). With `frame` off, the board renders at its natural rectangular size, capped to the container width, and centered (`margin-inline:auto`) — restoring the pre-replay play-page layout. The replay frame is unchanged.

## 0.6.0

### Minor Changes

- a344467: Poker replays go social-media-native at 16:9. `PokerReplay` renders the table inside the shared `ReplayFrame` with the `AspectSelect` switcher (alongside the existing POV dropdown), and passes real player names (`seatInfo`) so identity — name, stack, cards, status — lives on the table; the sidebar is dropped. The felt is a rounded-rectangle that fills the frame (header tucked in the top corners). In **9:16** the whole table spins 90° to fill the tall frame with cards/names counter-rotated upright and shrunk. In **1:1** the table centers with a stack leaderboard (chip + name + stack, sorted high→low, busted dimmed) in the letterbox bands. Picking a POV reveals/labels that seat without resizing it. `PokerReplay` gains optional `defaultRatio`/`ratios` (default 16:9); winner shown in the brand corner at game end.

## 0.5.0

### Minor Changes

- d0d442d: Blast replays go social-media-native at 1:1. The 13×11 board is padded to a true square (the grid is centered with an invisible same-color matte) so it renders natively at 1:1 inside the shared `ReplayFrame`, with the `AspectSelect` switcher in the playback controls — a replay can be re-framed to 16:9 / 9:16 for capture (the square board centers on a branded backdrop). The right-hand sidebar and the below-board HUD (and the per-player B/R/S powerup stats) are dropped for a clean clip: in native 1:1 each living player's name rides their character; in 16:9 / 9:16 identity moves to a roster legend (chip + name, dead dimmed) centered in the letterbox dead-space band. `BlastReplay` gains optional `defaultRatio`/`ratios` props (default 1:1); the winner shows in the frame's brand corner at game end.

## 0.4.0

### Minor Changes

- 54e4c09: Curve replays go social-media-native at 1:1. `CurveReplay` now renders its square board inside the shared `ReplayFrame` (native 1:1) with the `AspectSelect` switcher in the playback controls, so a replay can be re-framed to 16:9 / 9:16 for capture (the square board centers on a branded backdrop in those). The right-hand player-card sidebar is dropped; in native 1:1 each living player's name rides their curve head, pulsing very subtly in their seat color (a dead player has no head, so its label simply disappears — which is how alive/dead reads). `CurveReplay` gains optional `defaultRatio`/`ratios` props (default 1:1). The winner is shown in the frame's brand corner at game end.

  `ReplayFrame` also gains an optional `legend` prop: when a board is re-framed off its native ratio, the letterbox dead space is filled with a roster legend (color chip + name; dead players dimmed/struck-through). It's placed where social-video attention/safe-zones favor it — the left band when the frame is wider than native (pillarbox), the top band when it's taller (the bottom is the platform caption/action clutter zone). Curve uses this in 16:9 / 9:16 instead of on-head names.

## 0.3.0

### Minor Changes

- b1b7db1: Make replays social-media-shareable with selectable aspect ratios. Adds a shared `ReplayFrame` + `AspectSelect` (9:16 / 16:9 / 1:1) and renders the Vibelords board natively at 16:9 (the lane fills the clip, with a branded backdrop when re-framed). Units and keeps render substantially larger (1.8x) to fill the taller field and read better in clips, with each base's HP bar floating just above its own keep silhouette at any age. `VibelordsReplay` gains optional `defaultRatio`/`ratios` props (default 16:9) and drops its sidebar player cards — names, resources and base HP already read from the in-board HUD/keeps. The aspect selector sits in the playback controls; the framed region is a clean, branded rectangle for screen capture.

## 0.2.16

### Patch Changes

- 8ccae2a: Label players by `game_start.names` when the replay carries them (fallback: "seat N"); add a subtle vibewarz wordmark to the playback controls bar.

## 0.2.15

### Patch Changes

- 1876e4c: Add the Vibelords lane-RTS renderer — board, replay viewer, and asset sheet — plus `detectGameId` support for the `vibelords` game.

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
