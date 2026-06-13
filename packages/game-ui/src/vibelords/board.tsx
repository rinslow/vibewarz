"use client";

import { useState, type ReactNode } from "react";

import {
  AGE_NAMES,
  ageUpCost,
  unitDisplayName,
  type VibelordsBase,
  type VibelordsFx,
  type VibelordsPlayer,
  type VibelordsState,
  type VibelordsUnit,
  type VibelordsUnitType,
} from "./types";

// ── battlefield geometry (SVG units) ─────────────────────────────────────────
// The board renders natively at 16:9 (920×518) so a default replay is already a
// social-ready clip. Everything (keeps, units, HP bars) anchors to GROUND_Y and
// the ground band is the fixed slice below it, so the extra height over the old
// 360-tall board is sky headroom — which also hosts the HUD overlay.
const W = 920;
const H = 518; // 920:518 ≈ 16:9
const GROUND_BAND = 98; // ground slice below the horizon (unchanged)
const FIELD_L = 80; // x where lane position 0 maps (just outside the left keep)
const FIELD_R = W - 80; // x where lane position `length` maps
const GROUND_Y = H - GROUND_BAND; // top of the ground band; unit feet rest here
const KEEP_HALF = 40;
// Units and keeps render this much larger than their base art size, to fill the
// taller 16:9 field and read better in shareable clips. Applied at the feet so
// sprites/keeps grow upward and stay planted on the ground line.
const ASSET_SCALE = 1.8;
// Highest drawn point of each age's keep (raw units above the ground line):
// stone palisade, castle pennant, factory smokestack, future emitter orb. Used
// to float each base's HP bar just above its own silhouette rather than at a
// single height tuned for the tallest keep.
const KEEP_TOP_BY_AGE = [52, 122, 86, 121];

// Fixed star field [xFrac, yFrac (of sky), radius] scattered across the upper
// sky so the 16:9 headroom has some atmosphere. Avoids the moon's quadrant.
const SKY_STARS: ReadonlyArray<readonly [number, number, number]> = [
  [0.08, 0.18, 1.1], [0.15, 0.42, 0.8], [0.22, 0.12, 0.9], [0.31, 0.3, 1.2],
  [0.39, 0.16, 0.7], [0.46, 0.4, 1.0], [0.53, 0.22, 0.85], [0.6, 0.35, 0.7],
  [0.12, 0.6, 0.8], [0.27, 0.52, 0.7], [0.35, 0.66, 0.9], [0.5, 0.58, 0.8],
  [0.66, 0.5, 0.75], [0.7, 0.18, 0.9], [0.9, 0.46, 0.8], [0.95, 0.2, 0.7],
];

// Smooth-march duration — just under the 100ms tick so units glide between
// frames and arrive before the next tick resolves (same trick as Blast).
const MOVE_TRANSITION_MS = 90;

// All keyframes injected once — keeps the renderer self-contained.
const STYLE_SHEET = `
@keyframes aw-bob   { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-1.5px); } }
@keyframes aw-arrow { 0% { opacity: 0; } 25% { opacity: 1; } 100% { opacity: 0; } }
@keyframes aw-spark { 0% { opacity: 0; transform: scale(0.4); } 40% { opacity: 1; transform: scale(1.1); } 100% { opacity: 0; transform: scale(1.4); } }
@keyframes aw-puff  { 0% { opacity: 0.9; transform: scale(0.3); } 100% { opacity: 0; transform: scale(1.6); } }
@keyframes aw-strike{ 0% { opacity: 0; } 15% { opacity: 0.85; } 60% { opacity: 0.5; } 100% { opacity: 0; } }
@keyframes aw-drop  { 0% { transform: translateY(-120px); opacity: 0; } 30% { opacity: 1; } 100% { transform: translateY(0); opacity: 0.9; } }
@keyframes aw-glow  { 0%,100% { opacity: 0.55; } 50% { opacity: 1; } }
@keyframes aw-flag  { 0%,100% { transform: skewX(0deg); } 50% { transform: skewX(-7deg); } }
@keyframes aw-hue   { 0% { filter: hue-rotate(0deg); } 100% { filter: hue-rotate(360deg); } }
@keyframes aw-smoke { 0% { opacity: 0; transform: translateY(0) scale(0.6); } 30% { opacity: 0.5; } 100% { opacity: 0; transform: translateY(-22px) scale(1.5); } }
/* looping variants used by the asset-sheet review gallery — the effect stays
   visible for most of the cycle with only a short gap before it replays, so a
   reviewer rarely catches a blank frame. */
@keyframes aw-arrow-loop  { 0% { opacity: 0; } 8% { opacity: 1; } 80% { opacity: 1; } 95% { opacity: 0; } 100% { opacity: 0; } }
@keyframes aw-spark-loop  { 0% { opacity: 0; transform: scale(0.4); } 12% { opacity: 1; transform: scale(1.05); } 78% { opacity: 0; transform: scale(1.5); } 100% { opacity: 0; transform: scale(1.5); } }
@keyframes aw-puff-loop   { 0% { opacity: 0; transform: scale(0.3); } 10% { opacity: 0.9; transform: scale(0.55); } 78% { opacity: 0; transform: scale(1.6); } 100% { opacity: 0; transform: scale(1.6); } }
@keyframes aw-strike-loop { 0% { opacity: 0; } 8% { opacity: 0.85; } 78% { opacity: 0.4; } 93% { opacity: 0; } 100% { opacity: 0; } }
@keyframes aw-drop-loop   { 0% { transform: translateY(-120px); opacity: 0; } 12% { opacity: 1; } 42% { transform: translateY(0); opacity: 0.95; } 80% { transform: translateY(0); opacity: 0.9; } 93% { opacity: 0; } 100% { transform: translateY(0); opacity: 0; } }
.aw-bob   { animation: aw-bob 1s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
.aw-arrow { animation: aw-arrow 0.32s ease-out forwards; }
.aw-spark { animation: aw-spark 0.34s ease-out forwards; transform-origin: center; transform-box: fill-box; }
.aw-puff  { animation: aw-puff 0.5s ease-out forwards; transform-origin: center; transform-box: fill-box; }
.aw-strike{ animation: aw-strike 0.55s ease-out forwards; }
.aw-drop  { animation: aw-drop 0.5s ease-in forwards; }
.aw-glow  { animation: aw-glow 1.8s ease-in-out infinite; }
.aw-flag  { animation: aw-flag 2.2s ease-in-out infinite; transform-origin: top center; transform-box: fill-box; }
/* gatling barrels revolving around the firing axis: each barrel rides up/over/
   down/under, growing + brightening at the front, thin + dim at the back. Four
   barrels with staggered delays read as one spinning cluster. */
@keyframes aw-gatling { 0%,100% { transform: translateY(-2px) scaleY(0.55); opacity: 0.5; } 25% { transform: translateY(0) scaleY(1); opacity: 1; } 50% { transform: translateY(2px) scaleY(0.55); opacity: 0.5; } 75% { transform: translateY(0) scaleY(1); opacity: 0.38; } }
.aw-hue     { animation: aw-hue 7s linear infinite; }
.aw-smoke   { animation: aw-smoke 2.6s ease-out infinite; transform-origin: center; transform-box: fill-box; }
.aw-gatling { animation: aw-gatling 1s linear infinite; transform-origin: center; transform-box: fill-box; }
/* per-melee-unit signature idle/attack motions — one distinct loop each, so the
   eight melee bodies read apart at a glance (weapon swings/jabs, mount gaits). */
@keyframes aw-club   { 0% { transform: rotate(-52deg); } 38% { transform: rotate(-52deg); } 56% { transform: rotate(54deg); } 70% { transform: rotate(46deg); } 100% { transform: rotate(-52deg); } }
@keyframes aw-sling  { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
@keyframes aw-jab    { 0%,55%,100% { transform: translateX(0); } 30% { transform: translateX(3.6px); } }
@keyframes aw-level  { 0%,15% { transform: rotate(0deg); } 34% { transform: rotate(87deg); } 46% { transform: rotate(80deg); } 58% { transform: rotate(87deg); } 80% { transform: rotate(0deg); } 100% { transform: rotate(0deg); } }
@keyframes aw-draw   { 0% { transform: translateX(0); } 50% { transform: translateX(-7px); } 58% { transform: translateX(3px); } 66% { transform: translateX(0); } 100% { transform: translateX(0); } }
@keyframes aw-drawstring { 0% { transform: scaleX(1); } 50% { transform: scaleX(1.75); } 58% { transform: scaleX(1); } 100% { transform: scaleX(1); } }
@keyframes aw-recoil { 0%,100% { transform: translate(0,0); } 9% { transform: translate(-2.8px,0.7px); } 28% { transform: translate(0,0); } }
@keyframes aw-charge { 0%,60%,100% { transform: translateX(0); } 32% { transform: translateX(4.2px); } }
@keyframes aw-gallop { 0%,100% { transform: translateY(0) rotate(0deg); } 25% { transform: translateY(-2.6px) rotate(-2deg); } 55% { transform: translateY(0.7px) rotate(1.2deg); } 80% { transform: translateY(-1px) rotate(0deg); } }
@keyframes aw-canter { 0%,100% { transform: translateY(0) rotate(0deg); } 50% { transform: translateY(-1.3px) rotate(-0.8deg); } }
@keyframes aw-trot   { 0%,100% { transform: translateY(0) rotate(0deg); } 50% { transform: translateY(-2px) rotate(-1deg); } }
@keyframes aw-hover  { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-2.8px); } }
.aw-club   { animation: aw-club 1.4s ease-in-out infinite; transform-origin: left bottom; transform-box: fill-box; }
.aw-sling  { animation: aw-sling 0.5s linear infinite; transform-origin: left top; transform-box: fill-box; }
.aw-jab    { animation: aw-jab 1.5s ease-in-out infinite; }
.aw-level  { animation: aw-level 1.7s ease-in-out infinite; transform-origin: 30% 71%; transform-box: fill-box; }
.aw-draw   { animation: aw-draw 1.6s ease-in-out infinite; }
.aw-drawstring { animation: aw-drawstring 1.6s ease-in-out infinite; transform-origin: right center; transform-box: fill-box; }
.aw-recoil { animation: aw-recoil 1.4s ease-out infinite; }
.aw-charge { animation: aw-charge 1.9s ease-in-out infinite; }
.aw-gallop { animation: aw-gallop 0.7s ease-in-out infinite; transform-origin: center bottom; transform-box: fill-box; }
.aw-canter { animation: aw-canter 0.95s ease-in-out infinite; transform-origin: center bottom; transform-box: fill-box; }
.aw-trot   { animation: aw-trot 0.62s ease-in-out infinite; transform-origin: center bottom; transform-box: fill-box; }
.aw-hover  { animation: aw-hover 2s ease-in-out infinite; }
/* strike accents — VFX layered onto a body's attack motion. Each accent uses
   the SAME duration as the weapon keyframe it accompanies (so the two
   animations stay phase-locked for the life of the element) and flashes in
   the window where that weapon's strike lands:
     aw-club 1.4s lands ~56% · aw-jab 1.5s peaks 30% · aw-level 1.7s holds
     34–58% · aw-recoil 1.4s kicks 9% · aw-charge 1.9s peaks 32% · the hover
     beam glows on aw-glow's 1.8s cycle. */
@keyframes aw-club-swoosh { 0%,40% { opacity: 0; } 50% { opacity: 0.85; } 62% { opacity: 0.45; } 72%,100% { opacity: 0; } }
@keyframes aw-club-impact { 0%,53% { opacity: 0; transform: scale(0.35); } 58% { opacity: 0.95; transform: scale(1); } 68% { opacity: 0.55; transform: scale(1.18); } 78%,100% { opacity: 0; transform: scale(1.4); } }
@keyframes aw-jab-strike { 0%,16% { opacity: 0; transform: scale(0.5); } 30% { opacity: 0.95; transform: scale(1); } 42% { opacity: 0.4; } 54%,100% { opacity: 0; transform: scale(1.3); } }
@keyframes aw-level-strike { 0%,32% { opacity: 0; transform: scale(0.5); } 40% { opacity: 0.9; transform: scale(1); } 54% { opacity: 0.65; } 66%,100% { opacity: 0; transform: scale(1.3); } }
@keyframes aw-muzzle { 0%,4% { opacity: 0; transform: scale(0.45); } 9% { opacity: 0.95; transform: scale(1); } 20% { opacity: 0.5; } 32%,100% { opacity: 0; transform: scale(1.3); } }
@keyframes aw-charge-strike { 0%,20% { opacity: 0; transform: scale(0.55); } 32% { opacity: 0.95; transform: scale(1); } 44% { opacity: 0.4; } 56%,100% { opacity: 0; transform: scale(1.25); } }
@keyframes aw-beam-pulse { 0%,100% { opacity: 0.2; } 50% { opacity: 0.9; } }
.aw-club-swoosh { animation: aw-club-swoosh 1.4s ease-in-out infinite; }
.aw-club-impact { animation: aw-club-impact 1.4s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
.aw-jab-strike { animation: aw-jab-strike 1.5s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
.aw-level-strike { animation: aw-level-strike 1.7s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
.aw-muzzle { animation: aw-muzzle 1.4s ease-out infinite; transform-origin: center; transform-box: fill-box; }
.aw-charge-strike { animation: aw-charge-strike 1.9s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
.aw-beam-pulse { animation: aw-beam-pulse 1.8s ease-in-out infinite; }
/* locomotion — the MOVE state. Infantry legs stride (each leg swings about its
   hip, the two on opposite phases); the weapon strikes above are gated to the
   ATTACK state, so a body plays exactly one of march/strike at a time. */
@keyframes aw-stride { 0%,100% { transform: rotate(22deg); } 50% { transform: rotate(-22deg); } }
.aw-stride { animation: aw-stride 0.5s ease-in-out infinite; transform-origin: center top; transform-box: fill-box; }
`;

function hashId(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) & 0xffff;
  return h;
}

export function VibelordsBoard({
  state,
  mySeat,
  names = null,
}: {
  state: VibelordsState | null;
  mySeat: number | null;
  // Optional per-seat display names (string keys, as journaled in
  // game_start.names). Falls back to "seat N" labels when absent.
  names?: Record<string, string> | null;
}) {
  if (!state) {
    return <div className="vw-replay vw-replay__empty">waiting for board…</div>;
  }
  const length = state.lane.length;
  const px = (x: number) => FIELD_L + (x / length) * (FIELD_R - FIELD_L);
  // Tallest age on the field drives the dusk-sky tint, for a little escalation.
  const topAge = Math.max(0, ...state.players.map((p) => p.age));

  return (
    <div className="vw-replay vw-vibelords__board">
      <style>{STYLE_SHEET}</style>
      <ResourceHud state={state} mySeat={mySeat} names={names} />
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="vw-vibelords__svg"
        preserveAspectRatio="xMidYMid meet"
      >
        <Backdrop topAge={topAge} />

        {/* keeps (bases) */}
        {state.bases.map((b) => {
          const player = state.players[b.seat];
          return (
            <Keep
              key={`keep-${b.seat}`}
              base={b}
              age={player?.age ?? 0}
              color={player?.color ?? "#888"}
              cx={b.seat === 0 ? FIELD_L - 36 : FIELD_R + 36}
              scale={ASSET_SCALE}
            />
          );
        })}

        {/* units */}
        {state.units.map((u) => (
          <UnitSprite key={u.id} unit={u} cx={px(u.x)} color={colorOf(state, u.owner)} />
        ))}

        {/* transient fx (keyed by tick so animations restart each frame) */}
        {state.fx.map((fx, i) => (
          <Fx key={`fx-${state.tick}-${i}`} fx={fx} px={px} />
        ))}
      </svg>
    </div>
  );
}

function colorOf(state: VibelordsState, seat: number): string {
  return state.players[seat]?.color ?? "#888";
}

// ── backdrop ─────────────────────────────────────────────────────────────────

function Backdrop({ topAge }: { topAge: number }) {
  // Sky warms / darkens slightly as the ages advance.
  const horizon = ["#3a2f4a", "#3f3350", "#4a2f3e", "#2a3550"][topAge] ?? "#3a2f4a";
  return (
    <g>
      <defs>
        <linearGradient id="aw-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0a0a12" />
          <stop offset="70%" stopColor="#12111d" />
          <stop offset="100%" stopColor={horizon} />
        </linearGradient>
        <linearGradient id="aw-ground" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1a1812" />
          <stop offset="100%" stopColor="#0e0d0a" />
        </linearGradient>
      </defs>
      <rect x={0} y={0} width={W} height={GROUND_Y} fill="url(#aw-sky)" />
      {/* atmosphere — moon + stars fill the sky headroom so the 16:9 framing
          reads as intentional rather than empty. Fixed positions so nothing
          jitters between ticks. */}
      {SKY_STARS.map(([fx, fy, r], i) => (
        <circle
          key={`star-${i}`}
          cx={fx * W}
          cy={fy * GROUND_Y}
          r={r}
          fill="#cdd3f0"
          opacity={0.55}
        />
      ))}
      <circle cx={W * 0.8} cy={GROUND_Y * 0.26} r={34} fill="#1c1b2e" opacity={0.5} />
      <circle cx={W * 0.8} cy={GROUND_Y * 0.26} r={22} fill="#e8e4f5" opacity={0.92} />
      <circle cx={W * 0.8 - 7} cy={GROUND_Y * 0.26 - 4} r={18} fill="#cfd6ef" opacity={0.5} />
      {/* distant parallax hills */}
      <path
        d={`M0 ${GROUND_Y} Q ${W * 0.2} ${GROUND_Y - 60} ${W * 0.42} ${GROUND_Y - 18}
            T ${W * 0.8} ${GROUND_Y - 30} T ${W} ${GROUND_Y - 10} V ${GROUND_Y} Z`}
        fill="#181626"
        opacity={0.8}
      />
      <path
        d={`M0 ${GROUND_Y} Q ${W * 0.3} ${GROUND_Y - 34} ${W * 0.55} ${GROUND_Y - 8}
            T ${W} ${GROUND_Y - 20} V ${GROUND_Y} Z`}
        fill="#221f33"
        opacity={0.7}
      />
      {/* ground */}
      <rect x={0} y={GROUND_Y} width={W} height={H - GROUND_Y} fill="url(#aw-ground)" />
      <line x1={0} y1={GROUND_Y} x2={W} y2={GROUND_Y} stroke="#2c2a22" strokeWidth={1.5} />
      {/* faint centre line where armies clash */}
      <line
        x1={W / 2}
        y1={GROUND_Y - 6}
        x2={W / 2}
        y2={H}
        stroke="#ffffff10"
        strokeWidth={1}
        strokeDasharray="3 6"
      />
    </g>
  );
}

// ── keep / base ──────────────────────────────────────────────────────────────

function Keep({
  base,
  age,
  color,
  cx,
  scale = 1,
}: {
  base: VibelordsBase;
  age: number;
  color: string;
  cx: number;
  // Visual size multiplier for the building (the live board enlarges keeps to
  // fill the field; the asset-sheet gallery renders them at base scale = 1).
  scale?: number;
}) {
  const dead = base.hp <= 0;
  const hpFrac = Math.max(0, Math.min(1, base.hp / base.max_hp));
  // Float the bar just above this keep's own (scaled) silhouette + a small gap,
  // so it hugs the building at any age and any ASSET_SCALE.
  const keepTop = KEEP_TOP_BY_AGE[Math.max(0, Math.min(3, age))];
  const hpBarY = GROUND_Y - keepTop * scale - 15;
  return (
    <g opacity={dead ? 0.4 : 1}>
      {/* base HP bar floating above the keep */}
      <g transform={`translate(${cx}, ${hpBarY})`}>
        <rect x={-46} y={0} width={92} height={9} rx={3} fill="#000000aa" />
        <rect
          x={-44}
          y={2}
          width={88 * hpFrac}
          height={5}
          rx={2}
          fill={hpFrac > 0.5 ? "#a3e635" : hpFrac > 0.25 ? "#fbbf24" : "#f43f5e"}
        />
        <text
          x={0}
          y={-4}
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={9}
          fill={color}
        >
          {Math.max(0, Math.round(base.hp))}
        </text>
      </g>

      {/* building + shadow, enlarged about the ground anchor so the keep grows
          upward and stays planted (the HP bar above stays at UI scale). */}
      <g
        transform={`translate(${cx} ${GROUND_Y}) scale(${scale}) translate(${-cx} ${-GROUND_Y})`}
      >
        {/* shadow */}
        <ellipse cx={cx} cy={GROUND_Y + 3} rx={KEEP_HALF + 8} ry={6} fill="#00000066" />

        {/* each age has its own architecture — a different silhouette, not just a
            recoloured wall: a primitive palisade, a stone castle, a brick
            factory-fort, and a glowing energy citadel. */}
        {age <= 0 && <StoneFort cx={cx} color={color} />}
        {age === 1 && <CastleKeep cx={cx} color={color} />}
        {age === 2 && <Factory cx={cx} color={color} />}
        {age >= 3 && <FutureCitadel cx={cx} color={color} />}
      </g>
    </g>
  );
}

// Stone age — earthen rampart + timber palisade, thatched hut, skull totem.
function StoneFort({ cx, color }: { cx: number; color: string }) {
  const earth = "#3a2e1e";
  const log = "#5c3b1a";
  const logTop = "#6e4a22";
  const thatch = "#9a7338";
  const base = GROUND_Y;
  const logs = [-36, -27, -18, -9, 0, 9, 18, 27, 36];
  return (
    <g stroke="#0a0a0a" strokeWidth={1}>
      {/* earth rampart mound */}
      <path d={`M ${cx - 46} ${base} q 4 -20 16 -22 l 28 0 q 12 2 16 22 Z`} fill={earth} />
      {/* thatched hut roof peeking behind the wall */}
      <path d={`M ${cx - 15} ${base - 40} q 15 -17 30 0 Z`} fill={thatch} />
      <line x1={cx} y1={base - 51} x2={cx} y2={base - 40} stroke={logTop} strokeWidth={1.4} />
      {/* palisade logs with pointed caps + slight height variation */}
      {logs.map((lx, i) => {
        const h = 32 + ((i * 7) % 6);
        const top = base - 14 - h;
        return (
          <g key={i}>
            <rect x={cx + lx - 4} y={top + 4} width={8} height={h} fill={log} />
            <path d={`M ${cx + lx - 4} ${top + 4} l 4 -6 l 4 6 Z`} fill={logTop} />
            <line x1={cx + lx} y1={top + 7} x2={cx + lx} y2={top + h + 2} stroke="#0a0a0a" opacity={0.3} />
          </g>
        );
      })}
      {/* dark gateway with leaning log doors */}
      <rect x={cx - 10} y={base - 28} width={20} height={28} fill="#120d08" stroke="none" />
      <line x1={cx - 8} y1={base - 28} x2={cx - 4} y2={base} stroke={logTop} strokeWidth={2} />
      <line x1={cx + 8} y1={base - 28} x2={cx + 4} y2={base} stroke={logTop} strokeWidth={2} />
      {/* skull totem */}
      <line x1={cx + 41} y1={base} x2={cx + 41} y2={base - 30} stroke={logTop} strokeWidth={2.4} />
      <circle cx={cx + 41} cy={base - 34} r={4} fill="#e8e0c8" />
      <circle cx={cx + 39.5} cy={base - 34.5} r={1} fill="#0a0a0a" stroke="none" />
      <circle cx={cx + 42.5} cy={base - 34.5} r={1} fill="#0a0a0a" stroke="none" />
      {/* owner war-banner on a leaning pole */}
      <line x1={cx - 41} y1={base} x2={cx - 43} y2={base - 38} stroke={logTop} strokeWidth={2} />
      <path
        className="aw-flag"
        d={`M ${cx - 43} ${base - 38} l 13 2 l -3 5 l 3 5 l -13 2 Z`}
        fill={color}
        strokeWidth={1}
      />
    </g>
  );
}

// Castle age — tall crenellated stone keep, portcullis, arrow-slits, corner
// turret with a colour-roofed conical cap + pennant.
function CastleKeep({ cx, color }: { cx: number; color: string }) {
  const stone = "#6f6b64";
  const stoneDk = "#565249";
  const mortar = "#00000040";
  const base = GROUND_Y;
  const bodyTop = base - 86;
  const half = 32;
  const tx = cx + half - 4; // corner turret centre
  return (
    <g stroke="#0a0a0a" strokeWidth={1.5}>
      {/* main keep body */}
      <rect x={cx - half} y={bodyTop} width={half * 2} height={base - bodyTop} fill={stone} />
      {/* mortar courses */}
      {[0, 1, 2, 3].map((i) => (
        <line key={i} x1={cx - half} y1={bodyTop + 16 + i * 16} x2={cx + half} y2={bodyTop + 16 + i * 16} stroke={mortar} strokeWidth={1} />
      ))}
      {/* crenellated battlements */}
      {[-1.5, -0.5, 0.5, 1.5].map((i, k) => (
        <rect key={k} x={cx + i * 16 - 6} y={bodyTop - 10} width={12} height={12} fill={stone} stroke="#0a0a0a" strokeWidth={1.5} />
      ))}
      {/* arrow-slit windows with a warm glow */}
      {[-16, 14].map((wx, i) => (
        <g key={i}>
          <rect x={cx + wx - 2} y={bodyTop + 22} width={4} height={13} rx={1.5} fill="#1a140c" />
          <rect x={cx + wx - 1} y={bodyTop + 25} width={2} height={7} fill="#ffce7a" opacity={0.8} stroke="none" />
        </g>
      ))}
      {/* portcullis gate */}
      <path d={`M ${cx - 12} ${base} l 0 -20 a 12 12 0 0 1 24 0 l 0 20 Z`} fill="#1a140c" />
      {[-8, -4, 0, 4, 8].map((gx, i) => (
        <line key={i} x1={cx + gx} y1={base} x2={cx + gx} y2={base - 28} stroke="#3a3026" strokeWidth={1} />
      ))}
      {[0, 1, 2].map((i) => (
        <line key={`h${i}`} x1={cx - 11} y1={base - 6 - i * 8} x2={cx + 11} y2={base - 6 - i * 8} stroke="#3a3026" strokeWidth={1} />
      ))}
      {/* corner turret */}
      <rect x={tx - 9} y={base - 98} width={18} height={98} fill={stoneDk} stroke="#0a0a0a" strokeWidth={1.5} />
      <rect x={tx - 9} y={base - 98} width={18} height={5} fill={stone} stroke="none" />
      {/* conical roof in owner colour */}
      <path d={`M ${tx - 11} ${base - 98} l 11 -16 l 11 16 Z`} fill={color} stroke="#0a0a0a" strokeWidth={1.5} />
      <rect x={tx - 2} y={base - 86} width={4} height={9} rx={1.5} fill="#1a140c" />
      <rect x={tx - 1} y={base - 84} width={2} height={5} fill="#ffce7a" opacity={0.8} stroke="none" />
      {/* pennant */}
      <line x1={tx} y1={base - 114} x2={tx} y2={base - 122} stroke="#0a0a0a" strokeWidth={1.4} />
      <path className="aw-flag" d={`M ${tx} ${base - 122} l 12 3 l -4 4 l 4 4 l -12 3 Z`} fill={color} strokeWidth={1} />
    </g>
  );
}

// Industrial age — brick factory-fort: sawtooth roof, riveted steel bands,
// lit windows, a rolling steel gate, and smokestacks belching drifting smoke.
function Factory({ cx, color }: { cx: number; color: string }) {
  const brick = "#6e3b2e";
  const steel = "#3a3530";
  const base = GROUND_Y;
  const bodyTop = base - 60;
  const L = cx - 40;
  const R = cx + 26;
  const wcx = (L + R) / 2;
  return (
    <g stroke="#0a0a0a" strokeWidth={1.2}>
      {/* smokestacks behind the hall (drawn first so the hall overlaps their base) */}
      {[R - 1, R + 12].map((sx, i) => {
        const stackTop = base - 84 + i * 12;
        return (
          <g key={i}>
            <rect x={sx - 4} y={stackTop} width={8} height={base - stackTop} fill="#2a2622" stroke="#0a0a0a" strokeWidth={1.2} />
            <rect x={sx - 5} y={stackTop} width={10} height={4} fill="#7a4436" stroke="none" />
            <circle className="aw-smoke" style={{ animationDelay: `${i * 800}ms` }} cx={sx} cy={stackTop} r={5} fill="#b8b2a8" opacity={0.5} stroke="none" />
            <circle className="aw-smoke" style={{ animationDelay: `${i * 800 + 1300}ms` }} cx={sx + 2} cy={stackTop} r={4} fill="#9a948a" opacity={0.45} stroke="none" />
          </g>
        );
      })}
      {/* sawtooth north-light roof */}
      {[0, 1, 2].map((i) => {
        const sx = L + i * 22;
        return <path key={i} d={`M ${sx} ${bodyTop} l 0 -12 l 18 12 Z`} fill={steel} />;
      })}
      {/* main brick hall */}
      <rect x={L} y={bodyTop} width={R - L} height={base - bodyTop} fill={brick} />
      {/* brick courses */}
      {[0, 1, 2, 3].map((i) => (
        <line key={i} x1={L} y1={bodyTop + 12 + i * 12} x2={R} y2={bodyTop + 12 + i * 12} stroke="#00000033" />
      ))}
      {/* riveted steel corner bands */}
      <rect x={L} y={bodyTop} width={5} height={base - bodyTop} fill={steel} />
      <rect x={R - 5} y={bodyTop} width={5} height={base - bodyTop} fill={steel} />
      {[0, 1, 2, 3, 4].map((i) => (
        <circle key={i} cx={L + 2.5} cy={bodyTop + 10 + i * 12} r={1} fill="#9aa0a6" stroke="none" />
      ))}
      {/* painted owner placard */}
      <rect x={L + 9} y={bodyTop + 7} width={14} height={16} fill={color} stroke="#0a0a0a" strokeWidth={1} />
      <rect x={L + 9} y={bodyTop + 7} width={14} height={3} fill="#0a0a0a" opacity={0.3} stroke="none" />
      {/* lit windows flanking the gate */}
      {[-20, 20].map((wx, i) => (
        <g key={i}>
          <rect x={wcx + wx - 5} y={base - 30} width={10} height={20} fill="#1a120c" />
          <rect x={wcx + wx - 4} y={base - 29} width={8} height={18} fill="#ffb152" opacity={0.55} stroke="none" />
          <line x1={wcx + wx} y1={base - 30} x2={wcx + wx} y2={base - 10} stroke="#1a120c" strokeWidth={1} />
          <line x1={wcx + wx - 5} y1={base - 20} x2={wcx + wx + 5} y2={base - 20} stroke="#1a120c" strokeWidth={1} />
        </g>
      ))}
      {/* rolling steel gate */}
      <rect x={wcx - 10} y={base - 28} width={20} height={28} fill={steel} />
      {[0, 1, 2, 3].map((i) => (
        <line key={i} x1={wcx - 10} y1={base - 23 + i * 6} x2={wcx + 10} y2={base - 23 + i * 6} stroke="#0a0a0a" opacity={0.4} />
      ))}
    </g>
  );
}

// Future age — angular energy citadel. The whole glow group hue-cycles, so the
// citadel visibly shifts colour while it pulses — the era's signature look.
function FutureCitadel({ cx, color }: { cx: number; color: string }) {
  const chassis = "#1b2330";
  const chassisDk = "#141b26";
  const base = GROUND_Y;
  const bodyTop = base - 78;
  const half = 36;
  return (
    <g stroke="#0a0a0a" strokeWidth={1.5}>
      {/* angular chassis with chamfered top corners */}
      <path
        d={`M ${cx - half} ${base} L ${cx - half} ${base - 68} l 8 -10 l ${half * 2 - 16} 0 l 8 10 L ${cx + half} ${base} Z`}
        fill={chassis}
      />
      <rect x={cx - half + 6} y={bodyTop + 6} width={half * 2 - 12} height={base - bodyTop - 12} fill={chassisDk} />
      {/* owner-colour accent on the chamfers */}
      <path d={`M ${cx - half} ${base - 68} l 8 -10 l 6 0 l -8 10 Z`} fill={color} />
      <path d={`M ${cx + half} ${base - 68} l -8 -10 l -6 0 l 8 10 Z`} fill={color} />
      {/* hue-cycling glow group — windows, gate rim, and the emitter spire */}
      <g className="aw-hue">
        <rect x={cx - half + 10} y={bodyTop + 14} width={half * 2 - 20} height={3} rx={1.5} fill="#38bdf8" className="aw-glow" stroke="none" />
        <rect x={cx - half + 10} y={bodyTop + 28} width={half * 2 - 20} height={3} rx={1.5} fill="#38bdf8" className="aw-glow" stroke="none" />
        <rect x={cx - half + 10} y={bodyTop + 42} width={half * 2 - 20} height={3} rx={1.5} fill="#38bdf8" className="aw-glow" stroke="none" />
        {/* energised gate */}
        <path d={`M ${cx - 12} ${base} l 0 -18 a 12 12 0 0 1 24 0 l 0 18 Z`} fill="#0a1420" />
        <path d={`M ${cx - 12} ${base} l 0 -18 a 12 12 0 0 1 24 0 l 0 18 Z`} fill="none" stroke="#38bdf8" strokeWidth={1.6} className="aw-glow" />
        <rect x={cx - 9} y={base - 22} width={18} height={3} fill="#7dd3fc" opacity={0.7} className="aw-glow" stroke="none" />
        {/* energy spire with rings + emitter orb */}
        <rect x={cx - 2.5} y={base - 104} width={5} height={28} fill="#2a3340" stroke="none" />
        <rect x={cx - 1} y={base - 104} width={2} height={28} fill="#38bdf8" className="aw-glow" stroke="none" />
        <ellipse cx={cx} cy={base - 92} rx={11} ry={2.6} fill="#38bdf8" opacity={0.4} className="aw-glow" stroke="none" />
        <ellipse cx={cx} cy={base - 100} rx={7} ry={1.8} fill="#38bdf8" opacity={0.5} className="aw-glow" stroke="none" />
        <circle cx={cx} cy={base - 112} r={9} fill="#38bdf8" opacity={0.22} className="aw-glow" stroke="none" />
        <circle cx={cx} cy={base - 112} r={5.5} fill="#7dd3fc" className="aw-glow" stroke="none" />
      </g>
    </g>
  );
}

// ── units ────────────────────────────────────────────────────────────────────

// Each body plays one of two states. MOVE = marching/advancing (legs stride,
// mounts gait, weapon carried steady). ATTACK = striking/firing (weapon swings
// or shoots, locomotion settles). In live play we read the state off the unit's
// attack cooldown: a unit that just struck (atk_cd > 0) is engaged → ATTACK;
// otherwise it's still closing the distance → MOVE.
export type AnimMode = "move" | "attack";

// A single leg that strides only in MOVE. The two legs of a body pass opposite
// `delay`s so they swing out of phase (one forward while the other is back).
function StrideLeg({
  mode,
  delay,
  children,
}: {
  mode: AnimMode;
  delay?: number;
  children: ReactNode;
}) {
  return (
    <g
      className={mode === "move" ? "aw-stride" : ""}
      style={delay ? { animationDelay: `${delay}s` } : undefined}
    >
      {children}
    </g>
  );
}

function UnitSprite({
  unit,
  cx,
  color,
}: {
  unit: VibelordsUnit;
  cx: number;
  color: string;
}) {
  const face = unit.owner === 0 ? 1 : -1;
  const a = Math.max(0, Math.min(3, unit.age));
  const mode: AnimMode = unit.atk_cd > 0 ? "attack" : "move";
  // Later ages are physically larger — a Future mech towers over a caveman.
  const s = SIZE_BY_AGE[a] * ASSET_SCALE;
  // light vertical stagger so massed armies read with depth
  const lane = hashId(unit.id) % 3;
  const y = GROUND_Y + 2 + lane * 9;
  const hpFrac = Math.max(0, Math.min(1, unit.hp / unit.max_hp));
  const half = 9 * s;

  return (
    <g
      style={{
        transform: `translate(${cx}px, ${y}px)`,
        transition: `transform ${MOVE_TRANSITION_MS}ms linear`,
      }}
    >
      <ellipse cx={0} cy={1} rx={half} ry={2.4 * s} fill="#00000066" />
      <g style={{ transform: `scale(${face * s}, ${s})` }}>
        <g className="aw-bob">
          {unit.unit === "pike" && <PikeBody age={a} color={color} mode={mode} />}
          {unit.unit === "cavalry" && <CavalryBody age={a} color={color} mode={mode} />}
          {unit.unit === "archer" && <ArcherBody age={a} color={color} mode={mode} />}
          <AgePips age={a} />
        </g>
      </g>
      {/* hp pip */}
      <rect x={-half} y={3.5 * s + 1} width={2 * half} height={2.4} rx={1} fill="#000000aa" />
      <rect
        x={-half + 0.5}
        y={3.5 * s + 1.4}
        width={(2 * half - 1) * hpFrac}
        height={1.6}
        rx={1}
        fill={hpFrac > 0.5 ? color : hpFrac > 0.25 ? "#fbbf24" : "#f43f5e"}
      />
    </g>
  );
}

// Each age has its own dominant material + size so the four eras read at a
// glance: Stone = fur/bone (small, hunched), Castle = steel + plume (taller),
// Industrial = olive/gunmetal greatcoat, Future = dark chassis + cyan energy
// (largest). The owner `color` stays the torso/identity; everything else
// signals the age — silhouette, size, material, and (at Future) an energy glow.
const SIZE_BY_AGE = [0.95, 1.18, 1.34, 1.58];

// Approximate weapon-muzzle height in body coords (feet = 0) for each archer
// age — the sling hand, the nocked arrow, the rifle barrel, the railgun muzzle.
// Projectiles launch from muzzle * unit-scale so the shot leaves the weapon, not
// the waist. (Bigger later-age units fire from higher up.)
const MUZZLE_BODY_Y = [14, 18.5, 16, 18.5];

type AgePalette = {
  mat: string; // dominant age material (fur / steel / olive / chassis)
  wood: string; // hafts and shafts
  metal: string; // weapon/trim highlight (or cyan energy at Future)
  skin: string;
  glow: string | null; // Future energy accent
};
const AGE_PAL: AgePalette[] = [
  { mat: "#6b4f2a", wood: "#7a5a3a", metal: "#c8b27a", skin: "#e6c9a8", glow: null },
  { mat: "#9aa3ad", wood: "#7a5a3a", metal: "#e2e8f0", skin: "#e6c9a8", glow: null },
  { mat: "#5f6347", wood: "#3a2e22", metal: "#aab0bb", skin: "#e6c9a8", glow: null },
  { mat: "#1c2430", wood: "#2a3340", metal: "#7dd3fc", skin: "#dbeafe", glow: "#38bdf8" },
];

// Each body: feet at (0,0), facing right. A distinct silhouette per age — not
// just a weapon swap — so the eras are unmistakable even at small size.
function PikeBody({ age, color, mode }: { age: number; color: string; mode: AnimMode }) {
  const p = AGE_PAL[age];
  if (age === 0) {
    // Clubman — broad-shouldered brute, hide kilt, big stone-headed club
    return (
      <g stroke="#0a0a0a" strokeWidth={1}>
        {/* strike accents — a swoosh crescent along the club head's sweep
            (circle centred on the swing pivot (3,-13), radius ≈ 22, from the
            -52° windup to the +54° follow-through) and an impact burst where
            the blow lands. Phase-locked to aw-club via equal durations. */}
        {mode === "attack" && (
          <g className="aw-club-swoosh" stroke="none">
            <path d="M -5.2 -33.4 A 22 22 0 0 1 24.9 -15.3" fill="none" stroke="#e8e0c8" strokeWidth={4.6} strokeLinecap="round" opacity={0.32} />
            <path d="M -1 -34.5 A 22 22 0 0 1 24.9 -15.3" fill="none" stroke="#fff7d6" strokeWidth={2} strokeLinecap="round" />
          </g>
        )}
        {/* big stone club on the shoulder — hefted in a slow windup swing */}
        <g className={mode === "attack" ? "aw-club" : ""}>
          <line x1={3} y1={-13} x2={13} y2={-31} stroke={p.wood} strokeWidth={3} />
          <ellipse cx={14} cy={-32} rx={5.4} ry={6.4} fill="#8a7d64" />
          <ellipse cx={12} cy={-30} rx={1.6} ry={2} fill="#0a0a0a" opacity={0.25} />
        </g>
        {/* impact burst over the club face at the landing beat — drawn after
            the club so the flash pops on top of the stone head */}
        {mode === "attack" && (
          <g transform="translate(28, -13.5)" stroke="none">
            <g className="aw-club-impact">
              {[-42, -10, 22, 55].map((a) => {
                const r = (a * Math.PI) / 180;
                return (
                  <line
                    key={a}
                    x1={Math.cos(r) * 4}
                    y1={Math.sin(r) * 4}
                    x2={Math.cos(r) * 9.5}
                    y2={Math.sin(r) * 9.5}
                    stroke="#fff7d6"
                    strokeWidth={1.6}
                    strokeLinecap="round"
                  />
                );
              })}
              <circle cx={3.5} cy={6} r={1.6} fill="#9b8a6a" />
              <circle cx={-1.5} cy={7.5} r={1.1} fill="#8a7d64" />
            </g>
          </g>
        )}
        {/* stubby legs */}
        <StrideLeg mode={mode}>
          <rect x={-5} y={-7} width={4.2} height={7} fill="#0a0a0a" stroke="none" />
        </StrideLeg>
        <StrideLeg mode={mode} delay={-0.25}>
          <rect x={1.6} y={-7} width={4.2} height={7} fill="#0a0a0a" stroke="none" />
        </StrideLeg>
        {/* hide kilt */}
        <path d="M -7 -10 l 13 0 l -1.5 6 l -10 0 Z" fill={p.mat} />
        {/* broad hunched torso */}
        <path d="M -9 -20 q 9 -5 17 0 l -1 11 q -7 3 -15 0 Z" fill={color} />
        {/* fur mantle over the shoulders */}
        <path d="M -10 -19 q 10 -7 19 0 q -4 4 -9.5 4 q -5.5 0 -9.5 -4 Z" fill={p.mat} />
        <path d="M -9 -20 l -2 -4 l 3 2 Z" fill="#e8e0c8" />
        {/* head: heavy brow, wild hair, tusk necklace */}
        <circle cx={1} cy={-24} r={5} fill={p.skin} />
        <path d="M -4 -25 q 5 -7 10 0 q -2 -4 -5 -4 q -3 0 -5 4 Z" fill={p.mat} />
        <rect x={-3.5} y={-25} width={9} height={1.6} fill="#0a0a0a" opacity={0.35} />
        <path d="M -2 -19 l 1.6 3.2 l 1.6 -3.2 Z" fill="#e8e0c8" />
      </g>
    );
  }
  if (age === 1) {
    // Pikeman — tall, steel helm + plume, kite shield, long pike
    return (
      <g stroke="#0a0a0a" strokeWidth={1}>
        {/* long pike — lowered 90° to level for the strike, then raised back up */}
        <g className={mode === "attack" ? "aw-level" : ""}>
          <line x1={5} y1={-40} x2={7} y2={2} stroke={p.wood} strokeWidth={1.8} />
          <path d="M 5 -40 l 2.5 -6 l 2.5 6 Z" fill={p.metal} />
        </g>
        {/* strike accent — thrust flash where the pike points once aw-level
            lays it flat (tip lands at ≈(40.5,-12.7) for the 34–58% hold), so
            this is drawn at fixed coords rather than inside the rotating group */}
        {mode === "attack" && (
          <g className="aw-level-strike" stroke="none">
            <line x1={20} y1={-10.6} x2={33} y2={-11.4} stroke="#e8e8ea" strokeWidth={1} strokeLinecap="round" opacity={0.7} />
            <line x1={18} y1={-15} x2={31} y2={-15.8} stroke="#e8e8ea" strokeWidth={1} strokeLinecap="round" opacity={0.7} />
            {[-42, -10, 24, 56].map((a) => {
              const r = (a * Math.PI) / 180;
              return (
                <line
                  key={a}
                  x1={40.5 + Math.cos(r) * 2}
                  y1={-12.7 + Math.sin(r) * 2}
                  x2={40.5 + Math.cos(r) * 6.5}
                  y2={-12.7 + Math.sin(r) * 6.5}
                  stroke="#fff7d6"
                  strokeWidth={1.4}
                  strokeLinecap="round"
                />
              );
            })}
          </g>
        )}
        <StrideLeg mode={mode}>
          <rect x={-4} y={-7} width={3.2} height={7} fill={p.mat} />
        </StrideLeg>
        <StrideLeg mode={mode} delay={-0.25}>
          <rect x={1} y={-7} width={3.2} height={7} fill={p.mat} />
        </StrideLeg>
        <rect x={-5} y={-21} width={10} height={15} rx={2} fill={color} />
        <rect x={-6.5} y={-21} width={13} height={3.5} rx={1.5} fill={p.mat} />
        <path d="M -10 -19 q 4 -2 4 4 l 0 8 q 0 4 -4 5 q -2 -8 0 -17 Z" fill={color} stroke={p.metal} strokeWidth={1.1} />
        <circle cx={1} cy={-25} r={4.2} fill={p.skin} />
        <path d="M -3.5 -26 a 5 5 0 0 1 9 0 l 0 2 l -9 0 Z" fill={p.mat} />
        <path d="M 1 -30 q 5 -3 2 -9" fill="none" stroke={color} strokeWidth={2.4} />
      </g>
    );
  }
  if (age === 2) {
    // Trench Guard — greatcoat over boots, stahlhelm, bayonet rifle, webbing
    return (
      <g stroke="#0a0a0a" strokeWidth={1}>
        {/* rifle with fixed bayonet — kicks back on a recoil beat */}
        <g className={mode === "attack" ? "aw-recoil" : ""}>
          <line x1={6} y1={-7} x2={11} y2={-31} stroke="#2e2620" strokeWidth={2.4} />
          <line x1={10.4} y1={-29} x2={11.8} y2={-38} stroke={p.metal} strokeWidth={1.6} />
          <rect x={8.4} y={-20} width={3} height={1.8} fill="#2e2620" />
          {/* strike accent — muzzle flash + smoke off the barrel as it kicks */}
          {mode === "attack" && (
            <g className="aw-muzzle" stroke="none">
              <circle cx={12.2} cy={-39.6} r={2.4} fill="#fde047" opacity={0.9} />
              <line x1={13.4} y1={-41.2} x2={16.2} y2={-44.6} stroke="#fff7d6" strokeWidth={1.4} strokeLinecap="round" />
              <line x1={14.2} y1={-39.2} x2={18} y2={-40} stroke="#fff7d6" strokeWidth={1.2} strokeLinecap="round" />
              <line x1={11.2} y1={-42} x2={11.6} y2={-45.6} stroke="#fff7d6" strokeWidth={1.1} strokeLinecap="round" />
              <circle cx={14.6} cy={-44.4} r={1.5} fill="#9ca3af" opacity={0.5} />
            </g>
          )}
        </g>
        {/* boots below the coat */}
        <StrideLeg mode={mode}>
          <rect x={-4.5} y={-6} width={4} height={6} fill="#161310" stroke="none" />
        </StrideLeg>
        <StrideLeg mode={mode} delay={-0.25}>
          <rect x={1.4} y={-6} width={4} height={6} fill="#161310" stroke="none" />
        </StrideLeg>
        {/* flared greatcoat with a centre split */}
        <path d="M -7 -20 l 13 0 l 3 14 l -19 0 Z" fill={p.mat} />
        <line x1={0} y1={-18} x2={0} y2={-6} stroke="#0a0a0a" opacity={0.35} />
        {/* owner-colour collar + shoulders */}
        <path d="M -6 -20 q 6 -3 12 0 l -1.5 3.5 q -4.5 -2 -9 0 Z" fill={color} />
        {/* webbing strap + belt */}
        <line x1={-5.5} y1={-19} x2={5.5} y2={-9} stroke="#3a2e1f" strokeWidth={1.5} />
        <rect x={-7} y={-11} width={14} height={1.8} fill="#3a2e1f" />
        {/* head + stahlhelm dome with a flared brim */}
        <circle cx={1} cy={-24} r={4} fill={p.skin} />
        <path d="M -4.5 -24 a 5.5 5 0 0 1 11 0 Z" fill="#3f4330" />
        <path d="M -6 -23.5 q 7 2.4 13 0 l 0 1.5 q -6.5 2 -13 0 Z" fill="#33371f" />
      </g>
    );
  }
  // Juggernaut — hulking exosuit: piston legs, huge pauldrons, glowing reactor
  // core + visor, energy lance. The apex tank — big and imposing.
  return (
    <g stroke="#0a0a0a" strokeWidth={1}>
      {/* energy lance — glowing blade + tip, driven forward in a heavy charge */}
      <g className={mode === "attack" ? "aw-charge" : ""}>
        <line x1={12} y1={-42} x2={13} y2={-6} stroke={p.wood} strokeWidth={3} />
        <line x1={12} y1={-42} x2={13} y2={-22} stroke={p.metal} strokeWidth={3.4} className="aw-glow" />
        <path d="M 11.5 -44 l 1.5 -6 l 1.5 6 Z" fill={p.metal} className="aw-glow" />
        <circle cx={13} cy={-42} r={4.5} fill={p.glow ?? p.metal} opacity={0.3} className="aw-glow" />
        {/* strike accent — energy discharge crackling out of the lance-head
            glow orb at the charge's forward peak (flecks start outside the
            r=4.5 orb so they radiate from its rim, not across it) */}
        {mode === "attack" && (
          <g className="aw-charge-strike" stroke="none">
            {[-120, -65, -15, 30, 80].map((a) => {
              const r = (a * Math.PI) / 180;
              return (
                <line
                  key={a}
                  x1={13 + Math.cos(r) * 5.5}
                  y1={-42 + Math.sin(r) * 5.5}
                  x2={13 + Math.cos(r) * 9.5}
                  y2={-42 + Math.sin(r) * 9.5}
                  stroke="#e0f7ff"
                  strokeWidth={1.5}
                  strokeLinecap="round"
                />
              );
            })}
          </g>
        )}
      </g>
      {/* piston legs + heavy feet — heave forward and back as it stomps along */}
      <StrideLeg mode={mode}>
        <path d="M -7 -13 l -2 13 l 4 0 l 1 -11 Z" fill={p.mat} />
        <rect x={-10} y={-1} width={7} height={3} rx={1} fill={p.mat} />
      </StrideLeg>
      <StrideLeg mode={mode} delay={-0.25}>
        <path d="M 3 -13 l 2 13 l 4 0 l -1 -11 Z" fill={p.mat} />
        <rect x={3} y={-1} width={7} height={3} rx={1} fill={p.mat} />
      </StrideLeg>
      {/* hulking armoured torso */}
      <path d="M -10 -32 l 20 0 l 2 9 l -3 13 l -18 0 l -3 -13 Z" fill={color} />
      {/* massive pauldrons */}
      <path d="M -15 -32 q 6 -4 8 3 l -1 8 q -6 1 -8 -2 Z" fill={p.mat} />
      <path d="M 15 -32 q -6 -4 -8 3 l 1 8 q 6 1 8 -2 Z" fill={p.mat} />
      {/* chest vents + glowing reactor core (with halo) */}
      <rect x={-7} y={-28} width={14} height={2} fill="#0a0a0a" opacity={0.5} />
      <circle cx={0} cy={-19} r={4} fill={p.metal} className="aw-glow" />
      <circle cx={0} cy={-19} r={7.5} fill={p.glow ?? p.metal} opacity={0.22} className="aw-glow" />
      {/* angular helm + glowing visor band */}
      <path d="M -5.5 -41 l 11 0 l 1 6 l -2 2.5 l -9 0 l -2 -2.5 Z" fill={p.mat} />
      <rect x={-4.5} y={-38} width={9} height={2.4} fill={p.metal} className="aw-glow" />
      {/* antenna */}
      <line x1={4.5} y1={-41} x2={6.5} y2={-47} stroke={p.mat} strokeWidth={1.3} />
      <circle cx={6.5} cy={-47} r={1.6} fill={p.metal} className="aw-glow" />
    </g>
  );
}

function CavalryBody({ age, color, mode }: { age: number; color: string; mode: AnimMode }) {
  const p = AGE_PAL[age];
  if (age === 0) {
    // Wolf Rider — grey wolf mount, fur rider, bone spear (loping gallop)
    return (
      <g stroke="#0a0a0a" strokeWidth={1}>
        <g className={mode === "move" ? "aw-gallop" : ""}>
          {/* bone spear thrust forward on the charge */}
          <g className={mode === "attack" ? "aw-jab" : ""}>
            <line x1={2} y1={-18} x2={23} y2={-20} stroke={p.wood} strokeWidth={1.8} />
            <path d="M 23 -20 l 4 -1 l -3 3 Z" fill={p.metal} />
            {/* strike accent — speed lines along the shaft + a burst off the
                spear tip at the jab's peak (inside the jab group so the
                accent rides the thrust) */}
            {mode === "attack" && (
              <g className="aw-jab-strike" stroke="none">
                <line x1={10} y1={-23.2} x2={19} y2={-23.9} stroke="#fff7d6" strokeWidth={1} strokeLinecap="round" opacity={0.7} />
                <line x1={8} y1={-16.4} x2={17} y2={-17} stroke="#fff7d6" strokeWidth={1} strokeLinecap="round" opacity={0.7} />
                {[-40, -8, 26].map((a) => {
                  const r = (a * Math.PI) / 180;
                  return (
                    <line
                      key={a}
                      x1={26.5 + Math.cos(r) * 2}
                      y1={-20.5 + Math.sin(r) * 2}
                      x2={26.5 + Math.cos(r) * 6}
                      y2={-20.5 + Math.sin(r) * 6}
                      stroke="#fff7d6"
                      strokeWidth={1.3}
                      strokeLinecap="round"
                    />
                  );
                })}
              </g>
            )}
          </g>
          {[-8, -3, 5, 10].map((lx, i) => (
            <rect key={i} x={lx} y={-8} width={2.4} height={8} fill="#3a3a3a" stroke="none" />
          ))}
          <ellipse cx={1} cy={-13} rx={11} ry={5} fill="#6f6f6f" />
          <path d="M 10 -14 l 7 -5 l 2 3 l -4 6 Z" fill="#6f6f6f" />
          <path d="M 16 -19 l 1.6 -3.2 l 1.6 3.2 Z" fill="#6f6f6f" />
          <path d="M -9 -13 q -4 -1 -5 2" fill="none" stroke="#6f6f6f" strokeWidth={2} />
          <circle cx={-2} cy={-21} r={3.4} fill={p.skin} />
          <path d="M -5 -22 a 4 4 0 0 1 7 0 Z" fill={p.mat} />
          <rect x={-5} y={-19} width={7} height={6} rx={2} fill={color} />
        </g>
      </g>
    );
  }
  if (age === 1) {
    // Knight — steel-barded warhorse: four legs, an arched neck rising to a
    // proper horse head, flowing mane + tail, an owner-colour caparison, and an
    // upright rider with a level couched lance, pennant, and plumed great helm.
    const steel = "#9aa1ab";
    const steelDk = "#6e747e";
    const horsehair = "#3a3128";
    return (
      <g stroke="#0a0a0a" strokeWidth={1}>
        <g className={mode === "move" ? "aw-canter" : ""}>
          {/* couched jousting lance — thick tapered shaft, bell vamplate guard,
              three-prong coronel tip + pennant, driven forward in a joust */}
          <g className={mode === "attack" ? "aw-jab" : ""}>
            <path d="M -1 -21.5 L 29 -24.6 L 29 -22.4 L -1 -19.5 Z" fill="#cdd3db" stroke="#0a0a0a" strokeWidth={0.6} />
            <path d="M 2 -25 q -3.4 3.5 0 7 l 2.4 -0.3 q -2.6 -3 0 -6.4 Z" fill="#9aa1ab" stroke="#0a0a0a" strokeWidth={0.6} />
            <path d="M 29 -25.2 l 4.6 -1.2 m -4.6 1.2 l 4.6 0.4 m -4.6 -0.4 l 4.2 1.9" fill="none" stroke="#c7ccd4" strokeWidth={1.1} />
            <path d="M 8 -23.6 l 8 -0.9 l -1.8 2.4 l 1.8 2.4 l -8 0.9 Z" fill={color} />
            {/* strike accent — joust shock burst off the coronel + speed
                lines along the lance at the jab's peak */}
            {mode === "attack" && (
              <g className="aw-jab-strike" stroke="none">
                <line x1={13} y1={-28.6} x2={23} y2={-29.5} stroke="#e8e8ea" strokeWidth={1} strokeLinecap="round" opacity={0.7} />
                <line x1={11} y1={-17.6} x2={21} y2={-18.4} stroke="#e8e8ea" strokeWidth={1} strokeLinecap="round" opacity={0.7} />
                {[-42, -10, 24, 56].map((a) => {
                  const r = (a * Math.PI) / 180;
                  return (
                    <line
                      key={a}
                      x1={33 + Math.cos(r) * 2.5}
                      y1={-24.4 + Math.sin(r) * 2.5}
                      x2={33 + Math.cos(r) * 7}
                      y2={-24.4 + Math.sin(r) * 7}
                      stroke="#fff7d6"
                      strokeWidth={1.4}
                      strokeLinecap="round"
                    />
                  );
                })}
              </g>
            )}
          </g>
          {/* tail */}
          <path d="M -11 -16 q -6 0 -8 7 q 3 -2 5 -1 q -2 3 -1 6 q 5 -4 6 -11 Z" fill={horsehair} />
          {/* hind + fore legs */}
          <rect x={-9} y={-8} width={3} height={8} fill={steelDk} />
          <rect x={-4} y={-8} width={3} height={8} fill={steel} />
          <rect x={6} y={-8} width={3} height={8} fill={steelDk} />
          <rect x={11} y={-8} width={3} height={8} fill={steel} />
          {/* horse barrel (steel barding) */}
          <path d="M -11 -18 q 12 -5 22 0 q 2 4 0.5 8 l -22 0 q -2 -4 -0.5 -8 Z" fill={steel} />
          {/* caparison skirt (owner colour) with a scalloped hem */}
          <path d="M -11 -12 l 21 0 l 0 4 l -2.6 2 l -2.6 -2 l -2.6 2 l -2.6 -2 l -2.6 2 l -2.6 -2 l -2.4 2 Z" fill={color} />
          {/* arched neck */}
          <path d="M 8 -16 q 9 -1 12 -11 q 2.4 0.6 2.6 3.2 q -1.2 8 -8.6 12 Z" fill={steel} />
          {/* mane along the neck */}
          <path d="M 8 -17 q 8 -1 11 -9 q 1.2 0.4 1.6 1.6 q -3 7 -10 8.6 Z" fill={horsehair} />
          {/* head (chamfron) + ear + colour crest */}
          <path d="M 18 -26 l 6 -2.5 l 0.6 4.5 l -5 2.5 Z" fill={steel} />
          <path d="M 18 -27 l 1.2 -3.4 l 1.6 3.2 Z" fill={color} />
          <circle cx={23} cy={-24} r={0.9} fill="#0a0a0a" stroke="none" />
          {/* rider torso (owner colour) + pauldron */}
          <rect x={-3} y={-26} width={7} height={9} rx={1.6} fill={color} />
          <path d="M -4.5 -25 q 3 -2 5 1.5 l -1 3 q -3 0.5 -4.5 -1 Z" fill={steel} />
          {/* great helm (plume removed) */}
          <rect x={-3.5} y={-32} width={7.5} height={7} rx={2} fill={steel} />
          <rect x={-3.5} y={-29.6} width={7.5} height={1.4} fill="#0a0a0a" opacity={0.5} />
        </g>
      </g>
    );
  }
  if (age === 2) {
    // Dragoon — brown horse, saddlebag, peaked cap + carbine (brisk trot)
    return (
      <g stroke="#0a0a0a" strokeWidth={1}>
        <g className={mode === "move" ? "aw-trot" : ""}>
          {/* carbine — recoils as it fires */}
          <g className={mode === "attack" ? "aw-recoil" : ""}>
            <line x1={-2} y1={-20} x2={13} y2={-22} stroke={p.metal} strokeWidth={2} />
            {/* strike accent — muzzle flash + powder smoke on the recoil beat */}
            {mode === "attack" && (
              <g className="aw-muzzle" stroke="none">
                <circle cx={14.5} cy={-22.2} r={2.4} fill="#fde047" opacity={0.9} />
                <line x1={16.5} y1={-22.4} x2={20.5} y2={-22.8} stroke="#fff7d6" strokeWidth={1.4} strokeLinecap="round" />
                <line x1={15.8} y1={-24.4} x2={18.8} y2={-26.2} stroke="#fff7d6" strokeWidth={1.1} strokeLinecap="round" />
                <line x1={15.8} y1={-20.2} x2={18.8} y2={-18.6} stroke="#fff7d6" strokeWidth={1.1} strokeLinecap="round" />
                <circle cx={16} cy={-26.5} r={1.5} fill="#9ca3af" opacity={0.5} />
              </g>
            )}
          </g>
          {[-8, -3, 5, 10].map((lx, i) => (
            <rect key={i} x={lx} y={-8} width={2.4} height={8} fill="#4a3a28" stroke="none" />
          ))}
          <ellipse cx={1} cy={-14} rx={11} ry={5} fill="#7a5230" />
          <path d="M 10 -15 l 7 -7 l 3 2 l -5 8 Z" fill="#7a5230" />
          <rect x={-9} y={-13} width={6} height={5} rx={1} fill={p.mat} />
          <rect x={-5} y={-21} width={7} height={6} rx={2} fill={color} />
          <rect x={-5} y={-24} width={7} height={3} rx={1} fill={p.mat} />
        </g>
      </g>
    );
  }
  // Hover Striker — a UFO: a metallic saucer disc, a glowing cyan cockpit dome,
  // a ring of pulsing rim lights, an underglow halo, and a downward energy beam.
  return (
    <g stroke="#0a0a0a" strokeWidth={1}>
      {/* the whole saucer bobs gently as it hovers — a flyer never plants, so
          the hover runs in both states; only the strike beam is gated to ATTACK */}
      <g className="aw-hover">
        {/* downward energy beam — fired only while attacking. The wide cone
            idles on aw-glow; the bright core + ground flare pulse harder on
            the same 1.8s cycle so the strike reads as firing, not ambience. */}
        {mode === "attack" && (
          <>
            <path d="M -6 -10 l 12 0 l 7 10 l -26 0 Z" fill={p.glow ?? p.metal} opacity={0.16} className="aw-glow" />
            <path d="M -2.5 -10 l 5 0 l 3 10 l -11 0 Z" fill="#e0f7ff" className="aw-beam-pulse" stroke="none" />
            <ellipse cx={0} cy={0} rx={13} ry={2.2} fill={p.glow ?? p.metal} className="aw-beam-pulse" stroke="none" />
          </>
        )}
        {/* underglow halo */}
        <ellipse cx={0} cy={-7} rx={18} ry={3} fill={p.glow ?? p.metal} opacity={0.3} className="aw-glow" />
        {/* lower hull */}
        <ellipse cx={0} cy={-11} rx={18} ry={5} fill={p.mat} />
        {/* main saucer disc (owner colour) */}
        <ellipse cx={0} cy={-13.5} rx={18} ry={4.6} fill={color} />
        {/* rim lights */}
        {[-13, -6.5, 0, 6.5, 13].map((lx, i) => (
          <circle key={i} cx={lx} cy={-12.5} r={1.5} fill={p.glow ?? p.metal} className="aw-glow" />
        ))}
        {/* glowing cockpit dome */}
        <path d="M -7.5 -15.5 a 7.5 7 0 0 1 15 0 Z" fill="#7dd3fc" opacity={0.85} className="aw-glow" />
        <ellipse cx={0} cy={-15.5} rx={7.5} ry={1.6} fill={p.mat} />
        <circle cx={-2.5} cy={-19} r={1.6} fill="#ffffff" opacity={0.7} stroke="none" />
      </g>
    </g>
  );
}

function ArcherBody({ age, color, mode }: { age: number; color: string; mode: AnimMode }) {
  const p = AGE_PAL[age];
  if (age === 0) {
    // Slinger — light, fur, whirling a sling
    return (
      <g stroke="#0a0a0a" strokeWidth={1}>
        {/* sling whirled in a full circle around the hand before the release */}
        <g className={mode === "attack" ? "aw-sling" : ""}>
          <path d="M 5 -18 q 10 4 4 14" fill="none" stroke={p.wood} strokeWidth={1.2} />
          <circle cx={9} cy={-3} r={2} fill={p.wood} />
        </g>
        <StrideLeg mode={mode}>
          <rect x={-3.5} y={-6} width={3} height={6} fill="#0a0a0a" stroke="none" />
        </StrideLeg>
        <StrideLeg mode={mode} delay={-0.25}>
          <rect x={1} y={-6} width={3} height={6} fill="#0a0a0a" stroke="none" />
        </StrideLeg>
        <path d="M -4 -16 q 5 -2 9 0 l -1 10 q -4 1.5 -7 0 Z" fill={color} />
        <path d="M -5 -15 q 5 -4 10 0 q -2 2 -5 2 q -3 0 -5 -2 Z" fill={p.mat} />
        <circle cx={1} cy={-19} r={4} fill={p.skin} />
        <path d="M -3 -20 q 4 -5 8 0 Z" fill={p.mat} />
      </g>
    );
  }
  if (age === 1) {
    // Longbowman — very tall longbow, hood, quiver
    return (
      <g stroke="#0a0a0a" strokeWidth={1}>
        <path d="M 9 -32 q 13 14 0 27" fill="none" stroke={p.wood} strokeWidth={2} />
        {/* bowstring pinches back to the nock as he draws (scales about the
            bow tips, so the tips stay anchored to the stave) */}
        <g className={mode === "attack" ? "aw-drawstring" : ""}>
          <line x1={9} y1={-32} x2={1} y2={-18.5} stroke={p.metal} strokeWidth={0.8} />
          <line x1={9} y1={-5} x2={1} y2={-18.5} stroke={p.metal} strokeWidth={0.8} />
        </g>
        {/* nocked arrow — drawn back to the cheek, then loosed forward */}
        <g className={mode === "attack" ? "aw-draw" : ""}>
          <line x1={-2} y1={-18.5} x2={15} y2={-18.5} stroke={p.metal} strokeWidth={1.2} />
          <path d="M 15 -18.5 l -3 -1.6 m 3 1.6 l -3 1.6" fill="none" stroke={p.metal} strokeWidth={1} />
        </g>
        <StrideLeg mode={mode}>
          <rect x={-4} y={-7} width={3} height={7} fill={p.mat} />
        </StrideLeg>
        <StrideLeg mode={mode} delay={-0.25}>
          <rect x={1} y={-7} width={3} height={7} fill={p.mat} />
        </StrideLeg>
        <rect x={-7} y={-21} width={3} height={10} rx={1} fill={p.wood} />
        <rect x={-4} y={-20} width={9} height={13} rx={2} fill={color} />
        <circle cx={1} cy={-24} r={4} fill={p.skin} />
        <path d="M -3.5 -24 a 5 5 0 0 1 9 -1 l -1 3 Z" fill={p.mat} />
      </g>
    );
  }
  if (age === 2) {
    // Rifleman — shouldered rifle at aim, brodie helmet, olive coat
    return (
      <g stroke="#0a0a0a" strokeWidth={1}>
        {/* shouldered rifle — kicks back as it fires */}
        <g className={mode === "attack" ? "aw-recoil" : ""}>
          <line x1={-3} y1={-15} x2={17} y2={-16} stroke="#23271c" strokeWidth={2.4} />
          <line x1={13} y1={-16} x2={18} y2={-16} stroke={p.metal} strokeWidth={1.6} />
        </g>
        <StrideLeg mode={mode}>
          <rect x={-4} y={-7} width={3.2} height={7} fill="#23271c" stroke="none" />
        </StrideLeg>
        <StrideLeg mode={mode} delay={-0.25}>
          <rect x={1} y={-7} width={3.2} height={7} fill="#23271c" stroke="none" />
        </StrideLeg>
        <path d="M -5 -18 l 10 0 l 1.6 11 l -13.2 0 Z" fill={p.mat} />
        <rect x={-3} y={-17} width={6} height={9} rx={1} fill={color} />
        <circle cx={1} cy={-21} r={4} fill={p.skin} />
        <path d="M -4.5 -21 a 5.5 4.2 0 0 1 11 0 Z" fill={p.mat} />
        <ellipse cx={1} cy={-21} rx={6.5} ry={1.7} fill={p.mat} />
      </g>
    );
  }
  // Railgunner — sleek sniper with a long railgun: twin rails, a spinning
  // accelerator rotor mid-barrel, steady energy, muzzle bloom, visor.
  return (
    <g stroke="#0a0a0a" strokeWidth={1}>
      {/* twin rails */}
      <rect x={-3} y={-21} width={25} height={2} rx={1} fill={p.mat} />
      <rect x={-3} y={-16.5} width={25} height={2} rx={1} fill={p.mat} />
      {/* breech block at the back */}
      <rect x={-4} y={-21.5} width={4} height={7} rx={1} fill={p.mat} />
      {/* spinning gatling barrel cluster — four barrels revolve around the
          firing axis (between the rail shroud) on staggered phases */}
      {[0, 1, 2, 3].map((i) => (
        <rect
          key={i}
          className={mode === "attack" ? "aw-gatling" : ""}
          x={-1}
          y={-19.3}
          width={22}
          height={1.7}
          rx={0.8}
          fill={p.metal}
          style={{ animationDelay: `${-0.25 * i}s` }}
        />
      ))}
      {/* central spindle */}
      <circle cx={-1} cy={-18.5} r={1.5} fill={p.glow ?? p.metal} className="aw-glow" />
      {/* muzzle plate + a single blinking charge light (the old wide bloom
          halo is removed; this small core does the pulsing it used to) */}
      <rect x={20} y={-21.5} width={2.6} height={6} rx={1} fill={p.mat} />
      <circle cx={23} cy={-18.5} r={3} fill={p.glow ?? p.metal} className="aw-glow" />
      {/* legs */}
      <StrideLeg mode={mode}>
        <rect x={-5} y={-9} width={4} height={9} rx={1} fill={p.mat} />
      </StrideLeg>
      <StrideLeg mode={mode} delay={-0.25}>
        <rect x={1} y={-9} width={4} height={9} rx={1} fill={p.mat} />
      </StrideLeg>
      {/* sleek armoured torso + shoulder */}
      <path d="M -6 -25 l 11 0 l 1.5 9 l -2 8 l -10 0 l -1.5 -8 Z" fill={color} />
      <path d="M -8 -25 q 4 -2 6 2.5 l -1 5 q -4 1 -6 -1 Z" fill={p.mat} />
      {/* sleek helm + glowing visor */}
      <path d="M -5 -32 l 9 0 l 1 5 l -2 2.4 l -7 0 l -1 -2.4 Z" fill={p.mat} />
      <rect x={-4} y={-30} width={8} height={2.2} fill={p.metal} className="aw-glow" />
    </g>
  );
}

function AgePips({ age }: { age: number }) {
  if (age <= 0) return null;
  return (
    <g>
      {Array.from({ length: age }, (_, i) => (
        <circle key={i} cx={-4 + i * 4} cy={-30} r={1.4} fill="#fbbf24" />
      ))}
    </g>
  );
}

// ── transient fx ─────────────────────────────────────────────────────────────

function Fx({
  fx,
  px,
  fireY,
}: {
  fx: VibelordsFx;
  px: (x: number) => number;
  // Screen-y the projectile launches from. Defaults to the firing unit's
  // weapon-muzzle height at gameplay scale; the asset sheet passes the muzzle
  // height at its own (enlarged) scale so the shot lines up with the weapon.
  fireY?: number;
}) {
  if (fx.kind === "arrow") {
    // The "arrow" is the archer's projectile — it looks different per age:
    // a lobbed sling-stone, a fletched arrow, a flat bullet tracer, an energy
    // bolt. (Stone/arrow lob in a high arc; bullet/bolt fly flat.)
    const x0 = px(fx.x0);
    const x1 = px(fx.x1);
    const age = fx.age ?? 1;
    const dir = x1 >= x0 ? 1 : -1;
    const y = fireY ?? GROUND_Y - (MUZZLE_BODY_Y[age] ?? 16) * (SIZE_BY_AGE[age] ?? 1) * ASSET_SCALE;
    if (age <= 0) {
      // Slinger — a high lob + a tumbling stone landing at the target
      const midX = (x0 + x1) / 2;
      return (
        <g className="aw-arrow">
          <path d={`M ${x0} ${y} Q ${midX} ${y - 31} ${x1} ${y}`} fill="none" stroke="#9b8a6a" strokeWidth={1} strokeDasharray="1 3" opacity={0.7} />
          <circle cx={x1} cy={y} r={2.4} fill="#8a7d64" stroke="#0a0a0a" strokeWidth={0.6} />
        </g>
      );
    }
    if (age === 1) {
      // Longbowman — a fletched arrow arcing onto the target
      const midX = (x0 + x1) / 2;
      return (
        <g className="aw-arrow">
          <path d={`M ${x0} ${y} Q ${midX} ${y - 21} ${x1} ${y}`} fill="none" stroke={fx.crit ? "#a3e635" : "#caa14a"} strokeWidth={1.4} strokeLinecap="round" />
          <path d={`M ${x0} ${y - 1} l ${-dir * 4} -2.5 m ${dir * 4} 2.5 l ${-dir * 4} 2.5`} fill="none" stroke={fx.crit ? "#a3e635" : "#e8e8ea"} strokeWidth={1} />
          <path d={`M ${x1} ${y} l ${-dir * 5} -2.4 l 0 4.8 Z`} fill={fx.crit ? "#a3e635" : "#e8e8ea"} />
        </g>
      );
    }
    if (age === 2) {
      // Rifleman — an actual bullet in flight: a brass round with a short
      // motion-blur streak behind it, a muzzle flash at the barrel and an
      // impact spark at the target.
      const bx = x0 + (x1 - x0) * 0.62; // the round, partway to the target
      return (
        <g className="aw-arrow">
          {/* muzzle flash */}
          <circle cx={x0} cy={y} r={2.6} fill="#fde047" opacity={0.85} />
          {/* motion-blur streak trailing the round */}
          <line x1={bx - dir * 8} y1={y} x2={bx} y2={y} stroke={fx.crit ? "#fde047" : "#fbbf24"} strokeWidth={1.1} strokeLinecap="round" opacity={0.6} />
          {/* the bullet — brass casing-round with a bright nose */}
          <ellipse cx={bx} cy={y} rx={2.4} ry={1.1} fill={fx.crit ? "#fde047" : "#d9b25a"} stroke="#0a0a0a" strokeWidth={0.4} />
          <circle cx={bx + dir * 1.8} cy={y} r={1} fill="#fff7d6" />
          {/* impact spark */}
          <circle cx={x1} cy={y} r={1.6} fill="#fff7d6" />
        </g>
      );
    }
    // Railgunner — a glowing energy bolt: bloomed beam + bright core
    return (
      <g className="aw-arrow">
        <line x1={x0} y1={y} x2={x1} y2={y} stroke="#7dd3fc" strokeWidth={3.4} strokeLinecap="round" opacity={0.4} />
        <line x1={x0} y1={y} x2={x1} y2={y} stroke="#e0f7ff" strokeWidth={1.3} strokeLinecap="round" />
        <circle cx={x1} cy={y} r={3} fill="#7dd3fc" opacity={0.5} />
        <circle cx={x1} cy={y} r={1.4} fill="#ffffff" />
      </g>
    );
  }
  if (fx.kind === "hit") {
    // Position with the outer group's SVG transform attribute; the inner group
    // owns the scale/opacity animation (a CSS `transform: scale()` would
    // otherwise overwrite an inline translate and fling the spark to the origin).
    const x1 = px(fx.x1);
    return (
      <g transform={`translate(${x1}, ${GROUND_Y - 12})`}>
        <g className="aw-spark">
          {[0, 60, 120, 180, 240, 300].map((a) => {
            const r = (a * Math.PI) / 180;
            return (
              <line
                key={a}
                x1={0}
                y1={0}
                x2={Math.cos(r) * 6}
                y2={Math.sin(r) * 6}
                stroke={fx.crit ? "#fde047" : "#fca5a5"}
                strokeWidth={1.4}
              />
            );
          })}
        </g>
      </g>
    );
  }
  if (fx.kind === "death") {
    const x = px(fx.x);
    return (
      <g transform={`translate(${x}, ${GROUND_Y - 8})`}>
        <g className="aw-puff">
          <circle cx={0} cy={0} r={7} fill="#9ca3af55" />
          <circle cx={-4} cy={-3} r={4} fill="#9ca3af44" />
          <circle cx={4} cy={-2} r={4} fill="#9ca3af44" />
        </g>
      </g>
    );
  }
  // airstrike (the special) — the bombardment matches the caster's age:
  // a boulder volley, a flaming-arrow rain, an artillery barrage, an orbital
  // energy beam. A coloured warning band tints the struck half of the lane.
  const x0 = px(fx.x0);
  const x1 = px(fx.x1);
  const w = Math.abs(x1 - x0);
  const left = Math.min(x0, x1);
  const age = fx.age ?? 2;
  const bandColor = ["#a8895522", "#c2541e22", "#f43f5e22", "#38bdf822"][age] ?? "#f43f5e22";
  if (age >= 3) {
    // Future — a wide orbital beam that flashes down onto the band centre
    // (uses the strike-flash timing so it appears in place, not falling)
    const cx = left + w / 2;
    return (
      <g className="aw-strike">
        <rect x={left} y={0} width={w} height={GROUND_Y} fill={bandColor} />
        <rect x={cx - 12} y={0} width={24} height={GROUND_Y} fill="#7dd3fc" opacity={0.22} className="aw-glow" />
        <rect x={cx - 3.5} y={0} width={7} height={GROUND_Y} fill="#e0f7ff" opacity={0.9} />
        <ellipse cx={cx} cy={GROUND_Y} rx={Math.max(12, w * 0.42)} ry={7} fill="#7dd3fc" opacity={0.6} className="aw-glow" />
      </g>
    );
  }
  const drops = [0.18, 0.42, 0.62, 0.85];
  return (
    <g>
      <rect className="aw-strike" x={left} y={0} width={w} height={GROUND_Y} fill={bandColor} />
      {drops.map((f, i) => {
        const dx = left + w * f;
        if (age <= 0) {
          // Stone — falling boulders
          return (
            <g key={i} className="aw-drop" style={{ animationDelay: `${i * 80}ms` }}>
              <circle cx={dx} cy={GROUND_Y} r={4.5} fill="#6b5a44" stroke="#0a0a0a" strokeWidth={0.8} />
              <ellipse cx={dx - 1.4} cy={GROUND_Y - 1.4} rx={1.4} ry={1} fill="#8a7558" stroke="none" />
            </g>
          );
        }
        if (age === 1) {
          // Castle — flaming arrows streaking down
          return (
            <g key={i} className="aw-drop" style={{ animationDelay: `${i * 70}ms` }}>
              <line x1={dx - 4} y1={GROUND_Y - 22} x2={dx} y2={GROUND_Y} stroke="#fb923c" strokeWidth={1.8} strokeLinecap="round" />
              <circle cx={dx - 2} cy={GROUND_Y - 10} r={1.6} fill="#fde047" opacity={0.85} />
              <circle cx={dx} cy={GROUND_Y} r={2.4} fill="#f97316" />
            </g>
          );
        }
        // Industrial — artillery shells + bursts
        return (
          <g key={i} className="aw-drop" style={{ animationDelay: `${i * 90}ms` }}>
            <line x1={dx} y1={GROUND_Y - 18} x2={dx} y2={GROUND_Y - 5} stroke="#d1d5db" strokeWidth={2} />
            <circle cx={dx} cy={GROUND_Y} r={6} fill="#fb923c" opacity={0.4} />
            <circle cx={dx} cy={GROUND_Y} r={3.4} fill="#f43f5e" />
          </g>
        );
      })}
    </g>
  );
}

// ── top resource HUD ─────────────────────────────────────────────────────────

function ResourceHud({
  state,
  mySeat,
  names,
}: {
  state: VibelordsState;
  mySeat: number | null;
  names: Record<string, string> | null;
}) {
  return (
    <div className="vw-vibelords__hud">
      {state.players.map((p) => (
        <PlayerHudCard
          key={p.seat}
          player={p}
          base={state.bases[p.seat]}
          isMe={mySeat !== null && p.seat === mySeat}
          align={p.seat === 0 ? "left" : "right"}
          label={names?.[String(p.seat)] ?? `seat ${p.seat}`}
        />
      ))}
    </div>
  );
}

function PlayerHudCard({
  player,
  base,
  isMe,
  align,
  label,
}: {
  player: VibelordsPlayer;
  base: VibelordsBase | undefined;
  isMe: boolean;
  align: "left" | "right";
  label: string;
}) {
  const cost = ageUpCost(player.age);
  const specialReady = player.special_cd <= 0;
  const specialSecs = Math.ceil(player.special_cd / 10);
  const alive = !base || base.hp > 0;
  return (
    <div
      className={"vw-vibelords__hud-card" + (align === "right" ? " vw-vibelords__hud-card--right" : "")}
      style={{
        borderColor: alive ? player.color : "#333",
        backgroundColor: isMe ? `${player.color}14` : undefined,
        opacity: alive ? 1 : 0.5,
      }}
    >
      <div className="vw-vibelords__hud-top">
        <span className="vw-vibelords__hud-chip" style={{ backgroundColor: player.color }} />
        <span style={{ color: player.color }}>{label}</span>
        <span className="vw-vibelords__hud-age">{AGE_NAMES[player.age] ?? `age ${player.age}`}</span>
      </div>
      <div className="vw-vibelords__hud-stats">
        <span>
          ◎<span style={{ color: "#fbbf24" }}>{Math.round(player.gold)}</span>
        </span>
        <span>
          ✦<span style={{ color: "#38bdf8" }}>{player.xp}</span>
          {cost !== null && <span className="vw-vibelords__hud-dim">/{cost}</span>}
        </span>
        <span style={{ color: specialReady ? "#a3e635" : "var(--vw-color-text-muted)" }}>
          ✈{specialReady ? "rdy" : `${specialSecs}s`}
        </span>
      </div>
    </div>
  );
}

// ── asset sheet (review gallery) ────────────────────────────────────────────
// A labelled gallery of every drawn asset — all 12 unit sprites (3 roles × 4
// ages, shown true-to-scale), the four keeps, and the effects — so the art can
// be reviewed in one place.
const ASSET_ZOOM = 2.4;
const SEAT_GREEN = "#a3e635";

const cellBox = {
  border: "1px solid var(--vw-color-border)",
  borderRadius: 8,
  background: "var(--vw-color-surface)",
  padding: 8,
  margin: 0,
  textAlign: "center" as const,
};

export function VibelordsAssetSheet() {
  const types: VibelordsUnitType[] = ["pike", "cavalry", "archer"];
  const [mode, setMode] = useState<AnimMode>(
    typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).has("attack")
      ? "attack"
      : "move",
  );
  return (
    <div
      className="vw-replay"
      style={{
        background: "var(--vw-color-bg)",
        color: "var(--vw-color-text)",
        fontFamily: "var(--vw-font-mono)",
        padding: 24,
        minHeight: "100vh",
      }}
    >
      <style>{STYLE_SHEET}</style>
      {/* loop the transient fx continuously so they can be reviewed in motion
          (each plays its action then rests before repeating). aw-drop uses
          longhand props so the per-bomblet animation-delay stagger survives. */}
      <style>{
        ".vw-assets .aw-arrow{animation:aw-arrow-loop 1.3s ease-out infinite!important;}" +
        ".vw-assets .aw-spark{animation:aw-spark-loop 1.2s ease-out infinite!important;}" +
        ".vw-assets .aw-puff{animation:aw-puff-loop 1.2s ease-out infinite!important;}" +
        ".vw-assets .aw-strike{animation:aw-strike-loop 1.6s ease-out infinite!important;}" +
        ".vw-assets .aw-drop{animation-name:aw-drop-loop!important;animation-duration:1.6s!important;" +
        "animation-iteration-count:infinite!important;animation-fill-mode:none!important;}"
      }</style>
      <div className="vw-assets" style={{ maxWidth: 1120, margin: "0 auto" }}>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Vibelords — asset sheet</h1>
        <p style={{ opacity: 0.6, marginBottom: 16, fontSize: 13 }}>
          Every drawn asset, shown in seat-0 green. Tell me which to change.
        </p>

        <SheetSection title="Units — 3 roles × 4 ages (sized to scale)">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              margin: "0 0 12px",
            }}
          >
            <span style={{ fontSize: 12, opacity: 0.7 }}>Animation:</span>
            <div style={{ display: "inline-flex", border: "1px solid var(--vw-color-border)", borderRadius: 6, overflow: "hidden" }}>
              {(["move", "attack"] as AnimMode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  style={{
                    appearance: "none",
                    border: "none",
                    padding: "5px 14px",
                    fontFamily: "inherit",
                    fontSize: 12,
                    textTransform: "capitalize",
                    cursor: "pointer",
                    background: mode === m ? SEAT_GREEN : "transparent",
                    color: mode === m ? "#0c0c12" : "var(--vw-color-text)",
                    fontWeight: mode === m ? 700 : 400,
                  }}
                >
                  {m}
                </button>
              ))}
            </div>
            <span style={{ fontSize: 11, opacity: 0.5 }}>
              {mode === "move" ? "marching — legs stride, mounts gait, weapon carried" : "engaged — weapon strikes/fires, locomotion settles"}
            </span>
          </div>
          {[0, 1, 2, 3].map((age) => (
            <div key={age} style={{ marginBottom: 4 }}>
              <div style={{ fontSize: 12, opacity: 0.7, margin: "12px 0 6px" }}>
                {AGE_NAMES[age]} age
              </div>
              <Row>
                {types.map((t) => (
                  <UnitCell key={t} type={t} age={age} mode={mode} />
                ))}
              </Row>
            </div>
          ))}
        </SheetSection>

        <SheetSection title="Keeps (bases) — one per age">
          <Row>
            {[0, 1, 2, 3].map((age) => (
              <KeepCell key={age} age={age} />
            ))}
          </Row>
        </SheetSection>

        <SheetSection title="Shooters — archer firing its shot, one per age">
          <Row>
            {[0, 1, 2, 3].map((age) => (
              <ShooterCell key={age} age={age} />
            ))}
          </Row>
        </SheetSection>

        <SheetSection title="Airstrike (special) — one per age">
          <Row>
            {[0, 1, 2, 3].map((age) => (
              <FxCell
                key={age}
                label={`${AGE_NAMES[age]} bombardment`}
                fx={{ kind: "airstrike", owner: 0, age, x0: 12, x1: 128 }}
              />
            ))}
          </Row>
        </SheetSection>

        <SheetSection title="Melee & death">
          <Row>
            <FxCell
              label="hit — melee clash"
              fx={{ kind: "hit", owner: 0, x0: 70, x1: 70, crit: false }}
            />
            <FxCell
              label="death — unit lost"
              fx={{ kind: "death", owner: 0, unit: "pike", x: 70 }}
            />
          </Row>
        </SheetSection>
      </div>
    </div>
  );
}

function SheetSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ marginBottom: 28 }}>
      <h2
        style={{
          fontSize: 13,
          textTransform: "uppercase",
          letterSpacing: "0.15em",
          opacity: 0.7,
          marginBottom: 10,
          borderBottom: "1px solid var(--vw-color-border)",
          paddingBottom: 6,
        }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function Row({ children }: { children: ReactNode }) {
  return <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>{children}</div>;
}

function UnitCell({ type, age, mode }: { type: VibelordsUnitType; age: number; mode: AnimMode }) {
  const s = SIZE_BY_AGE[age] * ASSET_ZOOM;
  return (
    <figure style={{ ...cellBox, width: 180 }}>
      {/* extra room on the right and above (bodies face right, some weapons
          reach high) so attack-mode strike accents — swooshes, thrust
          flashes, impact bursts — aren't clipped at the cell edge. The
          Pikeman's leveled tip reaches the farthest: x ≈ 47 × 2.83 ≈ 133. */}
      <svg
        viewBox="-65 -200 205 220"
        width={164}
        height={176}
        style={{ display: "block", margin: "0 auto" }}
      >
        <line x1={-55} y1={0} x2={130} y2={0} stroke="#2c2a22" strokeWidth={1.5} />
        <ellipse cx={0} cy={2.5} rx={9 * s} ry={2.4 * s} fill="#00000055" />
        <g transform={`scale(${s})`}>
          {type === "pike" && <PikeBody age={age} color={SEAT_GREEN} mode={mode} />}
          {type === "cavalry" && <CavalryBody age={age} color={SEAT_GREEN} mode={mode} />}
          {type === "archer" && <ArcherBody age={age} color={SEAT_GREEN} mode={mode} />}
        </g>
      </svg>
      <figcaption style={{ fontSize: 12, marginTop: 6 }}>
        <div style={{ fontWeight: 700 }}>{unitDisplayName(type, age)}</div>
        <div style={{ opacity: 0.55, fontSize: 11 }}>
          {AGE_NAMES[age]} · {type}
        </div>
      </figcaption>
    </figure>
  );
}

function KeepCell({ age }: { age: number }) {
  return (
    <figure style={{ ...cellBox, width: 200 }}>
      <svg
        viewBox={`0 ${GROUND_Y - 148} 140 168`}
        width={180}
        height={216}
        style={{ display: "block", margin: "0 auto" }}
      >
        <line x1={0} y1={GROUND_Y} x2={140} y2={GROUND_Y} stroke="#2c2a22" strokeWidth={1.5} />
        <Keep base={{ seat: 0, x: 0, hp: 1100, max_hp: 1500 }} age={age} color={SEAT_GREEN} cx={70} />
      </svg>
      <figcaption style={{ fontSize: 12, marginTop: 6, fontWeight: 700 }}>
        {AGE_NAMES[age]} keep
      </figcaption>
    </figure>
  );
}

// A shooter cell pairs the archer body with the exact in-game projectile <Fx>,
// firing rightward out of the unit — so the shot reads as belonging to that
// shooter rather than floating in an empty box.
function ShooterCell({ age }: { age: number }) {
  const s = SIZE_BY_AGE[age] * 1.5;
  return (
    <figure style={{ ...cellBox, width: 256 }}>
      <svg
        viewBox={`0 ${GROUND_Y - 92} 212 108`}
        width={248}
        height={126}
        style={{ display: "block", margin: "0 auto", background: "#0c0c12", borderRadius: 4 }}
      >
        <line x1={0} y1={GROUND_Y} x2={212} y2={GROUND_Y} stroke="#2c2a22" strokeWidth={1.5} />
        <ellipse cx={26} cy={GROUND_Y + 2.5} rx={9 * s} ry={2.4 * s} fill="#00000055" />
        <g transform={`translate(26, ${GROUND_Y}) scale(${s})`}>
          {/* this section showcases the shot, so the body is in its attack state */}
          <ArcherBody age={age} color={SEAT_GREEN} mode="attack" />
        </g>
        {/* its shot, flying off to the right (looped by the asset-sheet css).
            fireY matches the muzzle at this cell's enlarged scale so the shot
            leaves the weapon, not the waist. */}
        <Fx
          fx={{ kind: "arrow", owner: 0, age, x0: 42, x1: 198, crit: false }}
          px={(x) => x}
          fireY={GROUND_Y - (MUZZLE_BODY_Y[age] ?? 16) * s}
        />
      </svg>
      <figcaption style={{ fontSize: 12, marginTop: 6, opacity: 0.8 }}>
        {unitDisplayName("archer", age)} — {AGE_NAMES[age]} · shot →
      </figcaption>
    </figure>
  );
}

function FxCell({ label, fx }: { label: string; fx: VibelordsFx }) {
  return (
    <figure style={{ ...cellBox, width: 200 }}>
      <svg
        viewBox={`0 ${GROUND_Y - 66} 140 80`}
        width={180}
        height={103}
        style={{ display: "block", margin: "0 auto", background: "#0c0c12", borderRadius: 4 }}
      >
        <line x1={0} y1={GROUND_Y} x2={140} y2={GROUND_Y} stroke="#2c2a22" strokeWidth={1.5} />
        <Fx fx={fx} px={(x) => x} />
      </svg>
      <figcaption style={{ fontSize: 12, marginTop: 6, opacity: 0.8 }}>{label}</figcaption>
    </figure>
  );
}
