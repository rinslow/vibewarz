"use client";

import type { CSSProperties } from "react";

import { Card, CardRow } from "./card";
import { ChipStack, DealerButton } from "./chip";
import type { PokerPlayer, PokerState } from "./types";

const MONO = "ui-monospace, 'JetBrains Mono', Menlo, Consolas, monospace";

export type SeatInfo = {
  seat: number;
  handle: string;
  is_bot: boolean;
  bot_label: string | null;
};

// Seat positions on the felt, expressed as percentages relative to the
// table div. Index 0 is always YOU (bottom-center); subsequent indices
// walk CLOCKWISE around the table — which, when viewed from above with
// YOU at the bottom, means going LEFT first (toward 7 o'clock). The
// engine convention is that seat+1 is the next-to-act / next-in-rotation
// seat, so offset 1 must be visually to your left.
const TABLE_POSITIONS: Record<number, { x: number; y: number }[]> = {
  2: [
    { x: 50, y: 88 },
    { x: 50, y: 12 },
  ],
  3: [
    { x: 50, y: 88 },
    { x: 10, y: 28 },
    { x: 90, y: 28 },
  ],
  4: [
    { x: 50, y: 88 },
    { x: 8, y: 50 },
    { x: 50, y: 10 },
    { x: 92, y: 50 },
  ],
  5: [
    { x: 50, y: 88 },
    { x: 10, y: 55 },
    { x: 25, y: 12 },
    { x: 75, y: 12 },
    { x: 90, y: 55 },
  ],
  6: [
    { x: 50, y: 88 },
    { x: 10, y: 62 },
    { x: 15, y: 18 },
    { x: 50, y: 8 },
    { x: 85, y: 18 },
    { x: 90, y: 62 },
  ],
};

const PHASE_LABEL: Record<string, string> = {
  between_hands: "shuffling",
  preflop: "preflop",
  flop: "flop",
  turn: "turn",
  river: "river",
  showdown: "showdown",
  hand_complete: "hand over",
  done: "tournament over",
};

const headerCell: CSSProperties = {
  fontFamily: MONO,
  fontSize: 12,
  textTransform: "uppercase",
  letterSpacing: "0.18em",
  color: "var(--vw-color-text-muted)",
};

function actionLabel(a: PokerPlayer["last_action"]): string | null {
  if (!a) return null;
  if (a.type === "fold") return "fold";
  if (a.type === "check") return "check";
  if (a.type === "call") return "call";
  if (a.type === "bet") return `bet ${(a as { amount: number }).amount}`;
  if (a.type === "raise") return `raise to ${(a as { to: number }).to}`;
  return null;
}

export function PokerBoard({
  state,
  mySeat,
  seatInfo,
  revealAll = false,
  rotate90 = false,
  emphasizeMe = true,
}: {
  state: PokerState | null;
  mySeat: number | null;
  seatInfo?: SeatInfo[];
  // Replay/spectator mode: show every seat's hole cards regardless of the
  // showdown flag. Live play always leaves this false so hidden info stays
  // hidden.
  revealAll?: boolean;
  // Enlarge the `mySeat` plate + cards (the live "this is you" treatment). Off
  // in replays so picking a POV doesn't resize that seat.
  emphasizeMe?: boolean;
  // Portrait (9:16): spin the whole landscape table 90° to fill the tall frame,
  // and counter-rotate the readable bits (cards/plates/pot) back to upright —
  // they end up smaller. The felt/oval turns; the content stays legible.
  rotate90?: boolean;
}) {
  const handleBySeat = new Map(seatInfo?.map((s) => [s.seat, s]) ?? []);
  if (!state) {
    return (
      <div
        style={{
          borderRadius: 16,
          padding: 48,
          textAlign: "center",
          color: "var(--vw-color-text-muted)",
          background: "linear-gradient(180deg, #1a1a1f 0%, #0a0a0b 100%)",
        }}
      >
        waiting for hand to start…
      </div>
    );
  }

  const N = state.players.length;
  const positions = TABLE_POSITIONS[N] ?? TABLE_POSITIONS[6];
  const anchor = mySeat ?? 0;
  const showdown = state.showdown_hands !== null || revealAll;
  // Portrait: counter-rotate every readable element so it stays upright while
  // the felt/oval spins. Cards shrink a notch to fit the narrower portrait.
  const cr = rotate90 ? " rotate(-90deg)" : "";

  // The landscape (16:9) table, identical in both orientations. In portrait it
  // gets spun 90° as a unit by the wrapper below.
  const table = (
    <div
      style={{
        position: "absolute",
        top: "8%",
        bottom: "5%",
        left: "5%",
        right: "5%",
        background:
          "radial-gradient(ellipse at center, #1f5840 0%, #0e3b27 65%, #082519 100%)",
        borderRadius: "16% / 26%",
        border: "10px solid",
        borderImage:
          "linear-gradient(135deg, #5b3a20 0%, #8a6233 35%, #3f2613 100%) 1",
        boxShadow:
          "inset 0 0 80px rgba(0,0,0,0.55), 0 12px 40px rgba(0,0,0,0.55)",
        overflow: "visible",
      }}
    >
      {/* Inner felt highlight to give the table some depth */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 12,
          pointerEvents: "none",
          borderRadius: "16% / 26%",
          boxShadow:
            "inset 0 0 0 1px rgba(255,255,255,0.04), inset 0 0 30px rgba(255,255,255,0.02)",
        }}
      />

      {/* Community cards + pot — center of table */}
      <div
        style={{
          position: "absolute",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "0.5rem",
          top: "44%",
          left: "50%",
          transform: `translate(-50%, -50%)${cr}`,
        }}
      >
        <div
          style={{
            fontFamily: MONO,
            fontSize: 10,
            textTransform: "uppercase",
            letterSpacing: "0.22em",
            color: "#9ca3af",
          }}
        >
          pot
        </div>
        <div style={{ fontFamily: MONO, fontSize: 20, fontWeight: 600, color: "#fff" }}>
          {state.pot}
        </div>
        <div style={{ marginTop: 4 }}>
          <CardRow cards={state.community_cards} empty={5} size={rotate90 ? "sm" : "md"} />
        </div>
      </div>

      {/* Per-seat positioning */}
      {state.players.map((player) => {
        const offset = (player.seat - anchor + N) % N;
        const pos = positions[offset];
        const info = handleBySeat.get(player.seat);
        return (
          <Seat
            key={player.seat}
            player={player}
            info={info}
            isMe={player.seat === mySeat}
            isButton={player.seat === state.button}
            isActor={player.seat === state.action_on}
            showdown={showdown}
            x={pos.x}
            y={pos.y}
            counterRotate={cr}
            compact={rotate90}
            emphasizeMe={emphasizeMe}
          />
        );
      })}

      {/* Showdown reveal panel */}
      {state.showdown_hands && (
        <div
          style={{
            position: "absolute",
            fontFamily: MONO,
            fontSize: 10,
            color: "#cbd5e1",
            background: "rgba(0,0,0,0.55)",
            borderRadius: 4,
            padding: "4px 8px",
            display: "flex",
            flexDirection: "column",
            gap: 2,
            top: "8px",
            left: "50%",
            transform: `translateX(-50%)${cr}`,
          }}
        >
          {Object.entries(state.showdown_hands).map(([seat, hand]) => (
            <div key={seat}>
              <span style={{ color: "var(--vw-color-text-muted)" }}>seat {seat} · </span>
              <span style={{ color: "#fff" }}>{hand}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    // Self-contained board so it fills the ReplayFrame natively (16:9), or 9:16
    // in portrait where the whole table is spun 90° to fill the tall frame. The
    // felt is inset so seat plates / dealer button / bet chips stay inside the
    // box and aren't clipped by the frame's overflow:hidden. Header sits in the
    // empty top corners (upright).
    <div
      className="vw-poker__board"
      style={{
        position: "relative",
        width: "100%",
        aspectRatio: rotate90 ? "9 / 16" : "16 / 9",
      }}
    >
      {/* Header — top corners */}
      <div
        style={{ position: "absolute", top: 6, left: 12, display: "flex", gap: "1rem", alignItems: "baseline", zIndex: 2 }}
      >
        <span style={{ ...headerCell, color: "var(--vw-color-accent)" }}>
          hand #{state.hand_number}
        </span>
        <span style={headerCell}>{PHASE_LABEL[state.phase] ?? state.phase}</span>
      </div>
      <div
        style={{ position: "absolute", top: 6, right: 12, display: "flex", gap: "1rem", alignItems: "baseline", zIndex: 2 }}
      >
        <span style={headerCell}>
          blinds {state.small_blind}/{state.big_blind}
        </span>
        <span style={headerCell}>level {state.level_idx ?? 0}</span>
      </div>

      {rotate90 ? (
        // A 16:9 table sized so that, spun 90°, its bounding box fills this 9:16
        // board (width 16/9 of the board width = the board height; height = the
        // board width). transform-origin center keeps it centered.
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: "177.78%",
            aspectRatio: "16 / 9",
            transform: "translate(-50%, -50%) rotate(90deg)",
            transformOrigin: "center",
          }}
        >
          {table}
        </div>
      ) : (
        table
      )}
    </div>
  );
}

function Seat({
  player,
  info,
  isMe,
  isButton,
  isActor,
  showdown,
  x,
  y,
  counterRotate = "",
  compact = false,
  emphasizeMe = true,
}: {
  player: PokerPlayer;
  info: SeatInfo | undefined;
  isMe: boolean;
  isButton: boolean;
  isActor: boolean;
  showdown: boolean;
  x: number;
  y: number;
  // Appended to each readable element's transform to keep it upright while the
  // table is spun in portrait (e.g. " rotate(-90deg)").
  counterRotate?: string;
  // Portrait: shrink cards a notch to fit the narrower frame.
  compact?: boolean;
  // Enlarge this seat when it's "me" (live treatment); off in replays.
  emphasizeMe?: boolean;
}) {
  // "me" still reveals cards + gets the YOU label/tint, but only grows in size
  // when emphasizeMe is on (live play) — so picking a replay POV doesn't resize.
  const meBig = isMe && emphasizeMe;
  const cardsVisible = isMe || showdown;
  const folded = player.folded;
  const cards = cardsVisible ? player.hole_cards : [];
  const placeholderCount = player.in_hand && !cardsVisible ? 2 : 0;
  const last = actionLabel(player.last_action);
  const cardSize = compact || !meBig ? "sm" : "lg";
  const dim = !player.in_hand;

  // Bet chips: positioned between this seat and table center (50, 44).
  const cx = 50;
  const cy = 44;
  const tBetChip = 0.3; // 30% of the way from seat to center
  const betX = x + (cx - x) * tBetChip;
  const betY = y + (cy - y) * tBetChip;

  // Dealer button: anchor at the seat plate, then push outward in pixels
  // along the seat→center direction. Pixel offsets are essential here —
  // the plate is sized in px (not %) so its share of the table changes
  // with the viewport.
  const seatToCenterLen = Math.hypot(cx - x, cy - y) || 1;
  const dirX = (cx - x) / seatToCenterLen;
  const dirY = (cy - y) / seatToCenterLen;
  const halfW = meBig ? 100 : 70;
  const halfH = meBig ? 78 : 62;
  const btnGapPx = 24;
  const btnOffsetPx =
    Math.min(
      Math.abs(dirX) > 1e-6 ? halfW / Math.abs(dirX) : Infinity,
      Math.abs(dirY) > 1e-6 ? halfH / Math.abs(dirY) : Infinity,
    ) + btnGapPx;

  const ringStyle: CSSProperties = isActor
    ? {
        boxShadow:
          "0 0 0 2px var(--vw-color-accent), 0 0 18px 4px rgba(163, 230, 53, 0.45)",
      }
    : { boxShadow: "0 4px 12px rgba(0,0,0,0.55)" };

  return (
    <>
      {/* Seat plate */}
      <div
        style={{
          position: "absolute",
          left: `${x}%`,
          top: `${y}%`,
          transform: `translate(-50%, -50%)${counterRotate}`,
          width: meBig ? 200 : 140,
          opacity: dim ? 0.55 : 1,
          transition: "opacity 200ms ease, box-shadow 220ms ease",
        }}
      >
        <div
          style={{
            borderRadius: 12,
            padding: 10,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 6,
            background:
              "linear-gradient(180deg, rgba(20,22,28,0.92), rgba(8,10,14,0.96))",
            border: "1px solid rgba(255,255,255,0.06)",
            ...ringStyle,
          }}
        >
          {/* Cards row — sits ABOVE the name strip so they read like a hand. */}
          {(cards.length > 0 || placeholderCount > 0) && (
            <div style={{ marginBottom: 2 }}>
              <CardRow
                cards={cards}
                empty={placeholderCount}
                size={cardSize}
                gap={isMe ? 6 : 3}
              />
            </div>
          )}
          {folded && cards.length === 0 && placeholderCount === 0 && (
            <div style={{ display: "flex", gap: 4 }}>
              {[0, 1].map((i) => (
                <Card key={i} card={null} size={cardSize} />
              ))}
            </div>
          )}

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              width: "100%",
              justifyContent: "center",
              fontFamily: MONO,
              fontSize: 12,
            }}
          >
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: 999,
                flexShrink: 0,
                background: player.color,
              }}
            />
            <span
              style={{
                color: "#fff",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                maxWidth: 140,
              }}
              title={info?.handle}
            >
              {info?.handle ?? `seat ${player.seat}`}
              {isMe && <span style={{ marginLeft: 4, color: "var(--vw-color-accent)" }}>· YOU</span>}
            </span>
            {info?.is_bot && !isMe && (
              <span
                style={{
                  fontSize: 9,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "var(--vw-color-text-muted)",
                }}
              >
                bot
              </span>
            )}
          </div>

          <div style={{ fontFamily: MONO, fontSize: 11, color: "#e2e8f0" }}>
            <span style={{ color: "var(--vw-color-text-muted)" }}>stack </span>
            <span>{player.stack}</span>
            {player.all_in && (
              <span style={{ marginLeft: 6, color: "var(--vw-color-danger)", fontWeight: 600 }}>
                ALL-IN
              </span>
            )}
            {folded && !player.all_in && (
              <span style={{ marginLeft: 6, color: "var(--vw-color-text-muted)" }}>folded</span>
            )}
            {!player.in_tournament && (
              <span style={{ marginLeft: 6, color: "var(--vw-color-danger)", textTransform: "uppercase" }}>
                out
              </span>
            )}
          </div>

          {last && (
            <div
              style={{
                fontFamily: MONO,
                fontSize: 10,
                color: "var(--vw-color-text-muted)",
                letterSpacing: "0.025em",
              }}
            >
              {last}
            </div>
          )}
        </div>
      </div>

      {/* Bet chip stack in front of the seat, on the felt */}
      {player.committed_round > 0 && (
        <div
          style={{
            position: "absolute",
            left: `${betX}%`,
            top: `${betY}%`,
            transform: `translate(-50%, -50%)${counterRotate}`,
          }}
        >
          <ChipStack amount={player.committed_round} />
        </div>
      )}

      {/* Dealer button — anchored at the seat percentage, then pushed out
          past the plate edge by a pixel offset so the gap stays consistent
          regardless of how the % seat plate scales. */}
      {isButton && (
        <div
          style={{
            position: "absolute",
            left: `${x}%`,
            top: `${y}%`,
            transform: `translate(-50%, -50%) translate(${dirX * btnOffsetPx}px, ${dirY * btnOffsetPx}px)${counterRotate}`,
          }}
        >
          <DealerButton />
        </div>
      )}
    </>
  );
}
