# @vibewarz/game-ui

React components for rendering [vibewarz](https://github.com/OmriGanor/vibewarz)
games. These are the same components the official platform's web UI uses —
extracted into a standalone package so the Python CLI (`vibewarz replay
--watch`) and any third-party tool render through the exact same code.

It ships two related things:

- **Replay viewers** — full playback UIs that take a replay event stream:
  `CurveReplay`, `BlastReplay`, `PokerReplay`.
- **Presentational boards** — the board renderers those viewers wrap, also
  used directly by the platform's live-play UI: `BlastBoard`, `PokerBoard`
  (plus `Card`, `CardRow`, `ChipStack`, `DealerButton`).

> **0.x is unstable.** Expect breaking changes between minor versions until
> 1.0.

## Status

| Game  | Replay viewer | Board        |
| ----- | ------------- | ------------ |
| Curve | `CurveReplay` | (canvas, internal) |
| Blast | `BlastReplay` | `BlastBoard` |
| Poker | `PokerReplay` | `PokerBoard` |

## Install

```bash
pnpm add @vibewarz/game-ui react react-dom
```

`react` and `react-dom` are peer dependencies (≥18).

## Use — replay viewer

```tsx
import { CurveReplay } from "@vibewarz/game-ui";
import "@vibewarz/game-ui/styles.css";

export function Replay({ events }) {
  return <CurveReplay events={events} />;
}
```

The `events` prop is the `events` array from a replay envelope:

```ts
type ReplayEnvelope = {
  match_id: string;
  game_id?: string;
  events: RawEvent[]; // GameStart | TickResult | GameEnd
};
```

— exactly the shape served by `GET /api/replays/{match_id}` from the
vibewarz platform, or by `vibewarz replay --watch` from the OSS CLI.

If you're loading from a generic JSONL file or unsure of the game, use
`detectGameId` to pick a renderer:

```tsx
import {
  CurveReplay,
  BlastReplay,
  PokerReplay,
  detectGameId,
  type RawReplay,
} from "@vibewarz/game-ui";

function Replay({ replay }: { replay: RawReplay }) {
  const game = detectGameId(replay);
  if (game === "curve") return <CurveReplay events={replay.events} />;
  if (game === "blast") return <BlastReplay events={replay.events} />;
  if (game === "poker") return <PokerReplay events={replay.events} />;
  return <p>no renderer for {game ?? "(unknown)"}</p>;
}
```

## Use — board (live play)

The boards are pure presentational components: pass a game state, they render
it. The platform's live-play client composes `PokerBoard` with its own action
controls; replays wrap the same board with playback controls.

```tsx
import { PokerBoard } from "@vibewarz/game-ui";
import "@vibewarz/game-ui/styles.css";

<PokerBoard state={state} mySeat={mySeat} seatInfo={seats} />;
```

## Theming

Components ship sensible dark-theme defaults. Override any of these CSS custom
properties on an ancestor element to re-skin:

```css
--vw-color-bg
--vw-color-surface
--vw-color-surface-2
--vw-color-border
--vw-color-text
--vw-color-text-muted
--vw-color-accent
--vw-color-danger
--vw-font-mono
--vw-radius
```

Example bridge from an app's own Tailwind theme tokens:

```tsx
<div
  style={{
    ["--vw-color-surface" as string]: "var(--color-surface)",
    ["--vw-color-text-muted" as string]: "var(--color-text-muted)",
    ["--vw-color-accent" as string]: "var(--color-accent)",
    ["--vw-color-danger" as string]: "var(--color-danger)",
  } as React.CSSProperties}
>
  <PokerBoard state={state} mySeat={null} revealAll />
</div>
```

All component class names are prefixed `vw-*` so the included `styles.css` is
safe to import alongside an app's own global CSS.

## Development

This package lives in the [vibewarz](https://github.com/OmriGanor/vibewarz)
monorepo. To iterate locally with a downstream consumer (e.g. the platform
web app) before publishing a release:

```bash
# In vibewarz-oss
pnpm install
pnpm -F @vibewarz/game-ui build

# In the consuming repo
pnpm add file:../vibewarz-oss/packages/game-ui
```

Publish via the `release-npm` workflow on merge to `main`; manual publishing
is not supported (see `.changeset/README.md`).
