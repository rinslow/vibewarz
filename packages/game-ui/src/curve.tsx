"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { PlaybackControls, usePlayback } from "./controls";
import { AspectSelect, ReplayFrame, ASPECT_RATIOS, type AspectRatio } from "./frame";
import { seatLabel, type RawEvent, type RawGameEndEvt } from "./types";

type PowerupKind = "speed" | "slow" | "god";
type Powerup = { id: string; kind: PowerupKind; x: number; y: number };
type Point = [number, number];

type CurvePlayer = {
  seat: number;
  x: number;
  y: number;
  heading_deg: number;
  alive: boolean;
  color: string;
  effects?: Partial<Record<PowerupKind, number>>;
};

type CurveState = {
  tick: number;
  arena: { w: number; h: number };
  speed: number;
  turn_rate_deg: number;
  players: CurvePlayer[];
  trails?: Point[][];
  trail_delta?: Point[][];
  placement: number[];
  powerups?: Powerup[];
};

// Per-frame state without the bulky trail arrays — trails are accumulated
// once into a single cumulative structure and sliced by `trailLens` at draw
// time (see buildCurveTimeline). Keeping per-frame state trail-free is what
// turns the in-memory cost from O(N²) into O(N).
type CurveStateLite = Omit<CurveState, "trails" | "trail_delta">;

const POWERUP_COLORS: Record<PowerupKind, string> = {
  speed: "#22c55e",
  slow: "#ef4444",
  god: "#a855f7",
};

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function powerupFill(kind: PowerupKind, tick: number): string {
  if (kind === "god") return `hsl(${(tick * 8) % 360}, 90%, 60%)`;
  return POWERUP_COLORS[kind];
}

// Engine default — keep in sync with games/.../curve/game.py POWERUP_DURATION.
const GOD_MAX_TICKS = 50;

type CurvePlayerLite = {
  seat: number;
  alive: boolean;
  color: string;
  effects?: Partial<Record<PowerupKind, number>>;
};

function headColor(
  player: CurvePlayerLite,
  all: readonly CurvePlayerLite[],
  tick: number,
): string {
  const effects = player.effects ?? {};

  if (effects.god && effects.god > 0) {
    const period = Math.max(2, Math.floor((effects.god / GOD_MAX_TICKS) * 10));
    return Math.floor(tick / period) % 2 === 0
      ? powerupFill("god", tick)
      : "#ffffff";
  }

  if (effects.speed && effects.speed > 0) return POWERUP_COLORS.speed;

  if (!(effects.slow && effects.slow > 0)) {
    const slowedByOther = all.some(
      (o) =>
        o.seat !== player.seat &&
        o.alive &&
        (o.effects?.slow ?? 0) > 0,
    );
    if (slowedByOther) return POWERUP_COLORS.slow;
  }

  return player.color;
}

type CurveFrame = { state: CurveStateLite; trailLens: number[] };

// One cumulative `trails` (built once) plus per-frame lightweight state and a
// per-seat point count. To draw frame i we render trails[seat][0..trailLens[i][seat]).
export type CurveTimeline = { trails: Point[][]; frames: CurveFrame[] };

function lite(s: CurveState): CurveStateLite {
  const { trails: _trails, trail_delta: _delta, ...rest } = s;
  return rest;
}

export function buildCurveTimeline(events: RawEvent[]): CurveTimeline {
  const frames: CurveFrame[] = [];
  // Single cumulative trail set, grown in place. Each frame records only the
  // per-seat lengths, so the whole timeline holds O(total points) + O(frames *
  // seats) — not a full trail snapshot per frame.
  let trails: Point[][] | null = null;

  for (const evt of events) {
    if (evt.type === "game_start") {
      const s = evt.state as CurveState;
      trails = (s.trails ?? s.players.map((p) => [[p.x, p.y] as Point])).map(
        (t) => t.map((pt) => [pt[0], pt[1]] as Point),
      );
      frames.push({ state: lite(s), trailLens: trails.map((t) => t.length) });
    } else if (evt.type === "tick_result") {
      if (!trails) continue;
      const s = evt.state as CurveState;
      const delta = s.trail_delta;
      if (delta && delta.length) {
        for (let seat = 0; seat < delta.length && seat < trails.length; seat++) {
          for (const pt of delta[seat]) {
            trails[seat].push([pt[0], pt[1]] as Point);
          }
        }
      } else if (s.trails) {
        // Back-compat / fallback: a replay that carries full cumulative trails
        // but no delta on this tick. Replace the cumulative set wholesale.
        trails = s.trails.map((t) => t.map((pt) => [pt[0], pt[1]] as Point));
      }
      frames.push({ state: lite(s), trailLens: trails.map((t) => t.length) });
    }
    // game_end: final state already shown via the last tick_result.
  }
  return { trails: trails ?? [], frames };
}

// Curve: tick_interval_ms=50 → 20 Hz live cadence.
const CURVE_TICKS_PER_SEC = 20;

// Curve's arena is square, so the board renders natively at 1:1 — that's the
// default replay ratio. The selector re-frames into the other social ratios.
const CURVE_NATIVE_RATIO: AspectRatio = "1:1";

export function CurveReplay({
  events,
  mySeat = null,
  defaultRatio = CURVE_NATIVE_RATIO,
  ratios = ASPECT_RATIOS,
}: {
  events: RawEvent[];
  // Seat the viewer played, so their name label reads a touch brighter.
  // null → neutral spectator view (no highlight).
  mySeat?: number | null;
  // Initial aspect ratio (defaults to the board's native 1:1). The selector
  // lets viewers re-frame into the other social ratios for capture.
  defaultRatio?: AspectRatio;
  ratios?: AspectRatio[];
}) {
  const { trails, frames } = useMemo(() => buildCurveTimeline(events), [events]);
  // Per-seat display names, resolved once — drawn on each player's curve head.
  const names = useMemo(() => {
    const seats = frames[0]?.state.players.map((p) => p.seat) ?? [];
    const max = seats.length ? Math.max(...seats) : -1;
    return Array.from({ length: max + 1 }, (_, seat) => seatLabel(events, seat));
  }, [events, frames]);
  const [ratio, setRatio] = useState<AspectRatio>(defaultRatio);
  const totalFrames = frames.length;
  const playback = usePlayback(totalFrames, CURVE_TICKS_PER_SEC);
  const current = frames[Math.min(playback.frame, Math.max(0, totalFrames - 1))];
  const finalPlacement =
    (events[events.length - 1] as RawGameEndEvt | undefined)?.placement ?? [];

  if (totalFrames === 0 || !current) {
    return <div className="vw-replay vw-replay__empty">empty replay</div>;
  }

  // Player identity now lives in-board (names ride their curve heads; a dead
  // player has no head, so its label vanishes). The only thing the dropped
  // sidebar still added is the final result — surface it as a brand line, but
  // only once playback reaches the end so it doesn't spoil the outcome.
  const winnerSeat = finalPlacement[0];
  const atEnd = playback.frame >= totalFrames - 1;
  const brand =
    atEnd && winnerSeat !== undefined ? (
      <span className="vw-frame__result">🏆 {seatLabel(events, winnerSeat)}</span>
    ) : undefined;

  // In the native 1:1 frame names ride the heads; in the re-framed ratios that
  // would crowd the board, so identity moves to a roster legend in the dead
  // space instead (ReplayFrame places it; greys out players as they die).
  const onHead = ratio === CURVE_NATIVE_RATIO;
  const legend = onHead ? undefined : (
    <>
      {current.state.players.map((p) => {
        const isMe = mySeat !== null && p.seat === mySeat;
        return (
          <span
            key={p.seat}
            className={
              "vw-frame__legend-item" +
              (p.alive ? "" : " vw-frame__legend-item--dead") +
              (isMe ? " vw-frame__legend-item--me" : "")
            }
          >
            <span
              className="vw-frame__legend-chip"
              style={{ backgroundColor: p.color }}
            />
            {names[p.seat] ?? `seat ${p.seat}`}
          </span>
        );
      })}
    </>
  );

  return (
    <div className="vw-replay">
      <ReplayFrame
        ratio={ratio}
        nativeRatio={CURVE_NATIVE_RATIO}
        brand={brand}
        legend={legend}
      >
        <CurveBoard
          state={current.state}
          trails={trails}
          trailLens={current.trailLens}
          names={names}
          mySeat={mySeat}
          showHeadLabels={onHead}
        />
      </ReplayFrame>
      <PlaybackControls
        totalFrames={totalFrames}
        currentTick={current.state.tick}
        maxTick={frames[totalFrames - 1].state.tick}
        playback={playback}
        extra={<AspectSelect value={ratio} options={ratios} onChange={setRatio} />}
      />
    </div>
  );
}

function CurveBoard({
  state,
  trails,
  trailLens,
  names,
  mySeat,
  showHeadLabels,
}: {
  state: CurveStateLite;
  trails: Point[][];
  trailLens: number[];
  // Per-seat display names, drawn riding each living player's curve head.
  names: string[];
  mySeat: number | null;
  // Whether to draw names on the heads (native 1:1 only — off-native ratios show
  // a roster legend in the letterbox dead space instead).
  showHeadLabels: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const size = 720; // logical drawing space (all px constants below are in it)

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // The backing buffer is a fixed square (RES×RES); CSS then meet-fits the
    // canvas into the ReplayFrame as a replaced element, preserving its 1:1
    // aspect from these intrinsic pixels (see .vw-curve__canvas). RES is large
    // enough to downscale-fill any frame, so the board stays crisp without
    // pinning a display size. Logical drawing stays in `size` units via the
    // RES/size transform, so all the px constants below are unchanged.
    const RES = 1440;
    const k = RES / size;
    canvas.width = RES;
    canvas.height = RES;
    ctx.setTransform(k, 0, 0, k, 0, 0);

    ctx.fillStyle = "#0a0a0b";
    ctx.fillRect(0, 0, size, size);

    ctx.strokeStyle = "#181820";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
      const p = (i / 10) * size;
      ctx.beginPath();
      ctx.moveTo(p, 0);
      ctx.lineTo(p, size);
      ctx.moveTo(0, p);
      ctx.lineTo(size, p);
      ctx.stroke();
    }

    ctx.strokeStyle = "#2a2a30";
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, size - 1, size - 1);

    const scale = size / state.arena.w;

    // Draw each seat's trail up to this frame's length — a prefix of the one
    // shared cumulative array, no per-frame copy.
    for (let seat = 0; seat < trails.length; seat++) {
      const len = trailLens[seat] ?? 0;
      if (len < 2) continue;
      const trail = trails[seat];
      const color = state.players[seat]?.color ?? "#fff";
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(trail[0][0] * scale, trail[0][1] * scale);
      for (let i = 1; i < len; i++) {
        ctx.lineTo(trail[i][0] * scale, trail[i][1] * scale);
      }
      ctx.stroke();
    }

    for (const pu of state.powerups ?? []) {
      const x = pu.x * scale;
      const y = pu.y * scale;
      const fill = powerupFill(pu.kind, state.tick);
      ctx.beginPath();
      ctx.arc(x, y, 12, 0, Math.PI * 2);
      ctx.fillStyle = fill + "33";
      ctx.fill();
      ctx.beginPath();
      ctx.arc(x, y, 6, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.fill();
    }

    for (const p of state.players) {
      if (!p.alive) continue;
      const x = p.x * scale;
      const y = p.y * scale;
      const head = headColor(p, state.players, state.tick);
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fillStyle = head;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(x, y, 10, 0, Math.PI * 2);
      ctx.fillStyle = head + "33";
      ctx.fill();
    }

    // Name labels ride each living player's head, pulsing VERY subtly so they
    // read without competing with the curves. A dead player has no head here,
    // so its label is simply absent — which is how alive/dead now reads. Only
    // in native 1:1; off-native ratios show the roster legend in the bands.
    if (showHeadLabels) {
      const pulse = 0.34 + 0.12 * Math.sin(state.tick * 0.18); // ≈ 0.22–0.46
      ctx.save();
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ctx.font = "600 11px ui-monospace, Menlo, Consolas, monospace";
      ctx.lineJoin = "round";
      const pad = 4;
      for (const p of state.players) {
        if (!p.alive) continue;
        const name = names[p.seat];
        if (!name) continue;
        // Clamp the (centered) label inside the canvas so heads at the walls
        // don't get their name clipped by the edge.
        const halfW = ctx.measureText(name).width / 2;
        const x = clamp(p.x * scale, halfW + pad, size - halfW - pad);
        const y = clamp(p.y * scale - 13, 14, size - pad); // just above the head
        const isMe = mySeat !== null && p.seat === mySeat;
        ctx.globalAlpha = isMe ? Math.min(1, pulse + 0.18) : pulse;
        // Faint dark outline for legibility over bright trails.
        ctx.strokeStyle = "#0a0a0b";
        ctx.lineWidth = 3;
        ctx.strokeText(name, x, y);
        ctx.fillStyle = p.color;
        ctx.fillText(name, x, y);
      }
      ctx.restore();
    }
  }, [state, trails, trailLens, names, mySeat, showHeadLabels]);

  return <canvas className="vw-curve__canvas" ref={canvasRef} />;
}
