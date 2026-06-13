"use client";

import { useEffect, useRef } from "react";

import { BOMB_FUSE_TICKS, type BlastPlayer, type BlastState } from "./types";

const TILE = 40;

function clampN(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}
const POWERUP_GLYPH: Record<string, string> = {
  bomb: "B",
  range: "R",
  speed: "S",
};
const POWERUP_COLOR: Record<string, string> = {
  bomb: "#a3e635",
  range: "#fbbf24",
  speed: "#38bdf8",
};

// Smooth-move duration. Slightly under the typical 200ms-per-tile cadence
// (cooldown=2 * 100ms tick) so the sprite arrives just before the next move
// command resolves — feels responsive without ever "snapping".
const MOVE_TRANSITION_MS = 180;

// All keyframe animations live in a single <style> block injected once by
// the board. Keeps the renderer self-contained — no external CSS toolchain.
const STYLE_SHEET = `
@keyframes bm-bob {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-2px); }
}
@keyframes bm-bomb-pulse {
  0%, 100% { transform: scale(1);   filter: drop-shadow(0 0 1px #a3e63566); }
  50%      { transform: scale(1.08); filter: drop-shadow(0 0 5px #a3e635cc); }
}
@keyframes bm-flame-flicker {
  0%, 100% { transform: rotate(0deg)   scale(1);   opacity: 0.9; }
  25%      { transform: rotate(-12deg) scale(1.1); opacity: 1.0; }
  50%      { transform: rotate(8deg)   scale(0.95); opacity: 0.85; }
  75%      { transform: rotate(-4deg)  scale(1.05); opacity: 1.0; }
}
@keyframes bm-powerup-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-3px); }
}
@keyframes bm-spark {
  0%, 100% { opacity: 0.3; transform: translateY(0) scale(1); }
  50%      { opacity: 1.0; transform: translateY(-2px) scale(1.3); }
}
.bm-bob      { animation: bm-bob 0.9s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
.bm-bomb     { animation: bm-bomb-pulse 0.6s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
.bm-flame    { animation: bm-flame-flicker 0.25s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
.bm-powerup  { animation: bm-powerup-float 1.4s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
.bm-spark    { animation: bm-spark 0.35s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
`;

type Facing = "up" | "down" | "left" | "right";

export function BlastBoard({
  state,
  mySeat,
  names = [],
  showNames = false,
  frame = false,
}: {
  state: BlastState | null;
  mySeat: number | null;
  // Per-seat display names, drawn riding each living character (native 1:1 only;
  // off-native ratios show a roster legend in the letterbox bands instead).
  names?: string[];
  showNames?: boolean;
  // Replay-frame mode: pad the board to a true square (native 1:1) with a large
  // intrinsic size so the shared ReplayFrame can meet-fit it. The live play page
  // leaves this false and renders the board at its natural rectangular size.
  frame?: boolean;
}) {
  // Track each seat's facing direction so the character's eyes can look
  // where they last moved. Recomputed from position deltas — the engine
  // doesn't ship a facing field and we don't need it server-side.
  const lastPosRef = useRef<Map<number, { x: number; y: number }>>(new Map());
  const facingRef = useRef<Map<number, Facing>>(new Map());

  useEffect(() => {
    if (!state) return;
    for (const p of state.players) {
      const prev = lastPosRef.current.get(p.seat);
      if (prev) {
        if (p.x > prev.x) facingRef.current.set(p.seat, "right");
        else if (p.x < prev.x) facingRef.current.set(p.seat, "left");
        else if (p.y > prev.y) facingRef.current.set(p.seat, "down");
        else if (p.y < prev.y) facingRef.current.set(p.seat, "up");
      }
      lastPosRef.current.set(p.seat, { x: p.x, y: p.y });
    }
  }, [state]);

  if (!state) {
    return <div className="vw-replay vw-replay__empty">waiting for board…</div>;
  }
  const { dims, board } = state;
  const width = dims.w * TILE;
  const height = dims.h * TILE;
  // Replay-frame mode pads the board to a true square so its native ratio is
  // exactly 1:1: the grid is centered with a matte top/bottom (same bg →
  // invisible seam), which lets the shared ReplayFrame meet-fit + legend band
  // math stay exact, and a large intrinsic size (vector) so CSS max-width/height
  // downscale-fills any frame crisply. The live play page renders the board at
  // its natural rectangular size (no padding) so it sits inline at a sane size.
  const side = Math.max(width, height);
  const vbW = frame ? side : width;
  const vbH = frame ? side : height;
  const padX = frame ? (side - width) / 2 : 0;
  const padY = frame ? (side - height) / 2 : 0;

  return (
    <>
      <style>{STYLE_SHEET}</style>
      <svg
        width={frame ? side * 2 : width}
        height={frame ? side * 2 : height}
        viewBox={`0 0 ${vbW} ${vbH}`}
        className={"vw-blast__svg" + (frame ? " vw-blast__svg--frame" : "")}
        style={{ background: "#0a0a0b" }}
      >
        <g transform={`translate(${padX} ${padY})`}>
          {/* tile layer */}
          {board.map((row, y) =>
            row.map((cell, x) => (
              <Tile key={`t-${x}-${y}`} cell={cell} x={x} y={y} />
            )),
          )}

          {/* powerups */}
          {state.powerups.map((pu) => (
            <Powerup key={`pu-${pu.id}`} kind={pu.kind} x={pu.x} y={pu.y} />
          ))}

          {/* bombs */}
          {state.bombs.map((b, i) => (
            <Bomb key={`bomb-${b.x}-${b.y}-${i}`} x={b.x} y={b.y} timer={b.timer} />
          ))}

          {/* flames */}
          {state.flames.map((f, i) => (
            <Flame key={`flame-${f.x}-${f.y}-${i}`} x={f.x} y={f.y} />
          ))}

          {/* characters */}
          {state.players.map((p) => (
            <Character
              key={`pl-${p.seat}`}
              player={p}
              facing={facingRef.current.get(p.seat) ?? "down"}
            />
          ))}

          {/* name labels ride each living character (native 1:1 only; off-native
              ratios surface identity via the ReplayFrame legend instead) */}
          {showNames &&
            state.players.map((p) => {
              if (!p.alive) return null;
              const name = names[p.seat];
              if (!name) return null;
              const isMe = mySeat !== null && p.seat === mySeat;
              // Clamp the centered label inside the board so wall-hugging
              // characters don't get their name clipped (estimate half-width).
              const halfW = (name.length * 7) / 2;
              const cx = clampN(p.x * TILE + TILE / 2, halfW + 4, width - halfW - 4);
              const cy = p.y * TILE + TILE / 2 - 20;
              return (
                <text
                  key={`nm-${p.seat}`}
                  x={cx}
                  y={cy}
                  textAnchor="middle"
                  fontFamily="ui-monospace, monospace"
                  fontSize={11}
                  fontWeight={700}
                  fill={p.color}
                  stroke="#0a0a0b"
                  strokeWidth={3}
                  paintOrder="stroke"
                  opacity={isMe ? 0.95 : 0.7}
                >
                  {name}
                </text>
              );
            })}
        </g>
      </svg>
    </>
  );
}

// ── tiles ──────────────────────────────────────────────────────────────────

function Tile({ cell, x, y }: { cell: string; x: number; y: number }) {
  const px = x * TILE;
  const py = y * TILE;
  if (cell === "hard") {
    return (
      <g>
        <rect x={px} y={py} width={TILE} height={TILE} fill="#1a2e05" />
        <rect
          x={px + 2}
          y={py + 2}
          width={TILE - 4}
          height={TILE - 4}
          fill="#1f3a08"
          stroke="#a3e635"
          strokeWidth={1.5}
        />
        {/* inner brick highlight */}
        <line
          x1={px + 4}
          y1={py + 4}
          x2={px + TILE - 4}
          y2={py + 4}
          stroke="#a3e63566"
          strokeWidth={1}
        />
        <line
          x1={px + 4}
          y1={py + 4}
          x2={px + 4}
          y2={py + TILE - 4}
          stroke="#a3e63566"
          strokeWidth={1}
        />
      </g>
    );
  }
  if (cell === "soft") {
    return (
      <g>
        <rect x={px} y={py} width={TILE} height={TILE} fill="#2a1607" />
        <rect
          x={px + 3}
          y={py + 3}
          width={TILE - 6}
          height={TILE - 6}
          fill="#5c360b"
          stroke="#78350f"
          strokeWidth={1}
        />
        {/* crack marks */}
        <line
          x1={px + 8}
          y1={py + 10}
          x2={px + TILE - 8}
          y2={py + 10}
          stroke="#3a2010"
          strokeWidth={1}
        />
        <line
          x1={px + 8}
          y1={py + 22}
          x2={px + 18}
          y2={py + 22}
          stroke="#3a2010"
          strokeWidth={1}
        />
        <line
          x1={px + 22}
          y1={py + 22}
          x2={px + TILE - 8}
          y2={py + 22}
          stroke="#3a2010"
          strokeWidth={1}
        />
      </g>
    );
  }
  return (
    <rect
      x={px}
      y={py}
      width={TILE}
      height={TILE}
      fill="#0f0f12"
      stroke="#16161a"
      strokeWidth={0.5}
    />
  );
}

// ── bombs ──────────────────────────────────────────────────────────────────

function Bomb({ x, y, timer }: { x: number; y: number; timer: number }) {
  const cx = x * TILE + TILE / 2;
  const cy = y * TILE + TILE / 2;
  const fuseFrac = Math.max(0, Math.min(1, timer / BOMB_FUSE_TICKS));
  // ring stroke-dashoffset traces the fuse running down.
  const ringR = TILE * 0.36;
  const C = 2 * Math.PI * ringR;
  return (
    <g>
      <g className="bm-bomb">
        <circle cx={cx} cy={cy + 1} r={TILE * 0.3} fill="#000000aa" />
        <circle
          cx={cx}
          cy={cy}
          r={TILE * 0.28}
          fill="#0a0a0a"
          stroke="#404040"
          strokeWidth={1.5}
        />
        <circle cx={cx - 4} cy={cy - 4} r={TILE * 0.07} fill="#a3a3a3" opacity={0.55} />
      </g>
      {/* fuse stem */}
      <line
        x1={cx}
        y1={cy - TILE * 0.28}
        x2={cx + 4}
        y2={cy - TILE * 0.42}
        stroke="#a3e635"
        strokeWidth={2}
        strokeLinecap="round"
      />
      {/* spark on top of fuse */}
      <circle
        cx={cx + 4}
        cy={cy - TILE * 0.42}
        r={2.5}
        fill="#fde68a"
        className="bm-spark"
      />
      {/* fuse-progress ring */}
      <circle
        cx={cx}
        cy={cy}
        r={ringR}
        fill="none"
        stroke="#a3e635"
        strokeWidth={2}
        strokeDasharray={C}
        strokeDashoffset={C * (1 - fuseFrac)}
        transform={`rotate(-90 ${cx} ${cy})`}
        opacity={0.85}
      />
    </g>
  );
}

// ── flames ─────────────────────────────────────────────────────────────────

function Flame({ x, y }: { x: number; y: number }) {
  const cx = x * TILE + TILE / 2;
  const cy = y * TILE + TILE / 2;
  return (
    <g>
      <rect
        x={x * TILE + 2}
        y={y * TILE + 2}
        width={TILE - 4}
        height={TILE - 4}
        fill="#fde68a22"
      />
      <g className="bm-flame">
        <path
          d={`M ${cx} ${cy - TILE * 0.38}
              C ${cx + 6} ${cy - TILE * 0.18}, ${cx + 6} ${cy - TILE * 0.05}, ${cx} ${cy}
              C ${cx - 6} ${cy - TILE * 0.05}, ${cx - 6} ${cy - TILE * 0.18}, ${cx} ${cy - TILE * 0.38} Z`}
          fill="#fde047"
        />
        <path
          d={`M ${cx - TILE * 0.38} ${cy}
              C ${cx - TILE * 0.18} ${cy - 6}, ${cx - TILE * 0.05} ${cy - 6}, ${cx} ${cy}
              C ${cx - TILE * 0.05} ${cy + 6}, ${cx - TILE * 0.18} ${cy + 6}, ${cx - TILE * 0.38} ${cy} Z`}
          fill="#fb923c"
        />
        <path
          d={`M ${cx + TILE * 0.38} ${cy}
              C ${cx + TILE * 0.18} ${cy - 6}, ${cx + TILE * 0.05} ${cy - 6}, ${cx} ${cy}
              C ${cx + TILE * 0.05} ${cy + 6}, ${cx + TILE * 0.18} ${cy + 6}, ${cx + TILE * 0.38} ${cy} Z`}
          fill="#fb923c"
        />
        <path
          d={`M ${cx} ${cy + TILE * 0.38}
              C ${cx + 6} ${cy + TILE * 0.18}, ${cx + 6} ${cy + TILE * 0.05}, ${cx} ${cy}
              C ${cx - 6} ${cy + TILE * 0.05}, ${cx - 6} ${cy + TILE * 0.18}, ${cx} ${cy + TILE * 0.38} Z`}
          fill="#fde047"
        />
        <circle cx={cx} cy={cy} r={4} fill="#ffffff" />
      </g>
    </g>
  );
}

// ── powerups ───────────────────────────────────────────────────────────────

function Powerup({ kind, x, y }: { kind: string; x: number; y: number }) {
  const cx = x * TILE + TILE / 2;
  const cy = y * TILE + TILE / 2;
  return (
    <g className="bm-powerup">
      <circle
        cx={cx}
        cy={cy}
        r={TILE * 0.32}
        fill={`${POWERUP_COLOR[kind]}22`}
        stroke={POWERUP_COLOR[kind]}
        strokeWidth={1.5}
      />
      <text
        x={cx}
        y={cy + 5}
        textAnchor="middle"
        fontFamily="ui-monospace, monospace"
        fontSize={14}
        fontWeight={700}
        fill={POWERUP_COLOR[kind]}
      >
        {POWERUP_GLYPH[kind]}
      </text>
    </g>
  );
}

// ── character ──────────────────────────────────────────────────────────────

/**
 * Each player is a little helmeted bomber: a colored head with a dark
 * visor and two eyes, a body in the same color, and feet. The whole
 * sprite bobs gently while idle and glides smoothly between tiles via a
 * CSS transition on the wrapper transform.
 */
function Character({
  player,
  facing,
}: {
  player: BlastPlayer;
  facing: Facing;
}) {
  if (!player.alive) return null;
  const cx = player.x * TILE + TILE / 2;
  const cy = player.y * TILE + TILE / 2;
  const color = player.color;

  // Eye offset based on facing — gives the character a sense of direction
  // without animating the whole body. Values are in SVG pixels relative to
  // the eye's idle position.
  const eyeOffset = {
    up: { x: 0, y: -1 },
    down: { x: 0, y: 1 },
    left: { x: -1.5, y: 0 },
    right: { x: 1.5, y: 0 },
  }[facing];

  return (
    <g
      style={{
        transform: `translate(${cx}px, ${cy}px)`,
        transition: `transform ${MOVE_TRANSITION_MS}ms linear`,
      }}
    >
      {/* drop shadow */}
      <ellipse cx={0} cy={13} rx={9} ry={2.5} fill="#00000066" />

      <g className="bm-bob">
        {/* feet */}
        <rect x={-7} y={9} width={5} height={3.5} fill="#0a0a0a" rx={1} />
        <rect x={2} y={9} width={5} height={3.5} fill="#0a0a0a" rx={1} />

        {/* body */}
        <rect
          x={-8}
          y={1}
          width={16}
          height={9}
          rx={2.5}
          fill={color}
          stroke="#0a0a0a"
          strokeWidth={1.2}
        />
        {/* belt highlight */}
        <rect x={-8} y={6} width={16} height={1.5} fill="#00000044" />

        {/* head (helmet) */}
        <circle cx={0} cy={-7} r={9.5} fill={color} stroke="#0a0a0a" strokeWidth={1.4} />
        {/* visor */}
        <rect x={-7} y={-9} width={14} height={6} rx={1.5} fill="#0a0a0a" />
        {/* eyes */}
        <circle cx={-3 + eyeOffset.x} cy={-6 + eyeOffset.y} r={1.6} fill="#ffffff" />
        <circle cx={3 + eyeOffset.x} cy={-6 + eyeOffset.y} r={1.6} fill="#ffffff" />
        {/* helmet shine */}
        <ellipse cx={-4} cy={-11} rx={2.5} ry={1.4} fill="#ffffff66" />

        {/* seat number on the chest */}
        <text
          x={0}
          y={8}
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={6.5}
          fontWeight={700}
          fill="#0a0a0a"
        >
          {player.seat}
        </text>
      </g>
    </g>
  );
}

