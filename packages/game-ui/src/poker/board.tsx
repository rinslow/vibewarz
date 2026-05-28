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
}: {
  state: PokerState | null;
  mySeat: number | null;
  seatInfo?: SeatInfo[];
  // Replay/spectator mode: show every seat's hole cards regardless of the
  // showdown flag. Live play always leaves this false so hidden info stays
  // hidden.
  revealAll?: boolean;
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

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {/* Header strip */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          flexWrap: "wrap",
          columnGap: "1.5rem",
          rowGap: "0.25rem",
          padding: "0 0.5rem",
        }}
      >
        <span style={{ ...headerCell, color: "var(--vw-color-accent)" }}>
          hand #{state.hand_number}
        </span>
        <span style={headerCell}>{PHASE_LABEL[state.phase] ?? state.phase}</span>
        <span style={headerCell}>
          blinds {state.small_blind}/{state.big_blind}
        </span>
        <span style={{ ...headerCell, marginLeft: "auto" }}>
          level {state.level_idx ?? 0}
        </span>
      </div>

      {/* The felt */}
      <div
        style={{
          position: "relative",
          width: "100%",
          aspectRatio: "16 / 10",
          background:
            "radial-gradient(ellipse at center, #1f5840 0%, #0e3b27 60%, #082519 100%)",
          borderRadius: "50% / 32%",
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
            borderRadius: "50% / 32%",
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
            transform: "translate(-50%, -50%)",
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
            <CardRow cards={state.community_cards} empty={5} size="md" />
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
              transform: "translateX(-50%)",
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
}: {
  player: PokerPlayer;
  info: SeatInfo | undefined;
  isMe: boolean;
  isButton: boolean;
  isActor: boolean;
  showdown: boolean;
  x: number;
  y: number;
}) {
  const cardsVisible = isMe || showdown;
  const folded = player.folded;
  const cards = cardsVisible ? player.hole_cards : [];
  const placeholderCount = player.in_hand && !cardsVisible ? 2 : 0;
  const last = actionLabel(player.last_action);
  const cardSize = isMe ? "lg" : "sm";
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
  const halfW = isMe ? 100 : 70;
  const halfH = isMe ? 78 : 62;
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
          transform: "translate(-50%, -50%)",
          width: isMe ? 200 : 140,
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
            transform: "translate(-50%, -50%)",
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
            transform: `translate(-50%, -50%) translate(${dirX * btnOffsetPx}px, ${dirY * btnOffsetPx}px)`,
          }}
        >
          <DealerButton />
        </div>
      )}
    </>
  );
}
