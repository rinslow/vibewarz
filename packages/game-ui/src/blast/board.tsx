"use client";

import { useEffect, useRef } from "react";

import { BOMB_FUSE_TICKS, type BlastPlayer, type BlastState } from "./types";

const TILE = 40;
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
}: {
  state: BlastState | null;
  mySeat: number | null;
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

  return (
    <div className="vw-replay vw-blast__board">
      <style>{STYLE_SHEET}</style>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="vw-blast__svg"
        style={{ background: "#0a0a0b" }}
      >
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
            isMe={mySeat !== null && p.seat === mySeat}
            facing={facingRef.current.get(p.seat) ?? "down"}
          />
        ))}
      </svg>

      <PlayerHud state={state} mySeat={mySeat} />
    </div>
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
  isMe,
  facing,
}: {
  player: BlastPlayer;
  isMe: boolean;
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
      {/* halo for "this is you" */}
      {isMe && (
        <circle r={TILE * 0.46} fill={`${color}1a`} stroke={color} strokeWidth={1} opacity={0.6} />
      )}
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

// ── HUD ────────────────────────────────────────────────────────────────────

function PlayerHud({
  state,
  mySeat,
}: {
  state: BlastState;
  mySeat: number | null;
}) {
  return (
    <div className="vw-blast__hud">
      {state.players.map((p) => {
        const isMe = mySeat !== null && p.seat === mySeat;
        return (
          <div
            key={p.seat}
            className="vw-blast__hud-card"
            style={{
              borderColor: p.alive ? p.color : "#333",
              opacity: p.alive ? 1 : 0.4,
            }}
          >
            <div className="vw-blast__hud-row">
              <span style={{ color: p.color }}>seat {p.seat}</span>
              {isMe && <span className="vw-blast__hud-you">you</span>}
            </div>
            <div className="vw-blast__hud-stats">
              <span>
                B<span style={{ color: "#a3e635" }}>{p.bombs_max}</span>
              </span>
              <span>
                R<span style={{ color: "#fbbf24" }}>{p.blast_range}</span>
              </span>
              <span>
                S<span style={{ color: "#38bdf8" }}>{3 - p.move_cooldown}</span>
              </span>
              {!p.alive && <span className="vw-blast__hud-dead">dead</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
