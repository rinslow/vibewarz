"use client";

import type { CSSProperties } from "react";

import { seatLabel, type RawEvent } from "../types";
import type { RpsAction, RpsPiece, RpsState } from "./types";

const PIECE_LABEL: Record<string, string> = {
  unassigned: "?",
  rock: "R",
  paper: "P",
  scissors: "S",
  trap: "T",
  flag: "F",
  hidden: "?",
};

const PIECE_NAME: Record<string, string> = {
  unassigned: "unassigned",
  rock: "rock",
  paper: "paper",
  scissors: "scissors",
  trap: "trap",
  flag: "flag",
  hidden: "hidden",
};

function squareName(square: number): string {
  const file = String.fromCharCode("a".charCodeAt(0) + (square % 8));
  const rank = Math.floor(square / 8) + 1;
  return `${file}${rank}`;
}

function pieceColor(piece: RpsPiece | null): string {
  if (!piece) return "transparent";
  return piece.color === 0 ? "#f43f5e" : "#38bdf8";
}

function describeAction(action: unknown): string | null {
  const a = action as Partial<RpsAction> | undefined;
  if (!a || typeof a !== "object") return null;
  if (a.type === "setup") return "setup";
  if (a.type === "fight") return `fight ${(a as { piece?: string }).piece ?? ""}`.trim();
  if (a.type === "pass") return "pass";
  if (a.type === "move") {
    const move = a as { from?: number; to?: number; move_type?: string };
    if (typeof move.from === "number" && typeof move.to === "number") {
      return `${squareName(move.from)} -> ${squareName(move.to)}${move.move_type === "capture" ? " capture" : ""}`;
    }
  }
  return null;
}

export function RpsBoard({
  state,
  events,
  actions,
}: {
  state: RpsState;
  events: RawEvent[];
  actions?: Record<string, unknown>;
}) {
  const lastMove = Object.values(actions ?? {}).find(
    (action): action is RpsAction =>
      !!action && typeof action === "object" && (action as RpsAction).type === "move",
  );
  const from = lastMove?.type === "move" ? lastMove.from : null;
  const to = lastMove?.type === "move" ? lastMove.to : null;
  const winner =
    state.winner === null || state.winner === undefined
      ? null
      : seatLabel(events, state.winner);

  return (
    <div style={wrapStyle}>
      <div style={hudStyle}>
        {state.players.map((player) => (
          <div
            key={player.seat}
            style={{
              ...playerStyle,
              borderColor: player.color_hex,
              opacity: state.winner === null || state.winner === player.seat ? 1 : 0.45,
            }}
          >
            <span style={{ ...chipStyle, background: player.color_hex }} />
            <strong>{seatLabel(events, player.seat)}</strong>
            <span style={mutedStyle}>
              {state.phase === "fight" && player.fight_commit ? "committed" : `seat ${player.seat}`}
            </span>
          </div>
        ))}
      </div>

      <div style={statusStyle}>
        <span>tick {state.tick}</span>
        <span>{state.phase}</span>
        {state.phase === "play" && <span>turn {seatLabel(events, state.current_turn)}</span>}
        {state.phase === "fight" && state.fight_location !== null && (
          <span>fight at {squareName(state.fight_location)}</span>
        )}
        {winner && <span>winner {winner}</span>}
      </div>

      <div style={boardWrapStyle}>
        <div style={filesStyle}>
          <span />
          {"abcdefgh".split("").map((file) => (
            <span key={file}>{file}</span>
          ))}
        </div>
        <div style={gridWithRanksStyle}>
          {Array.from({ length: 8 }, (_, row) => {
            const rank = 8 - row;
            return (
              <div key={`rank-${rank}`} style={rankRowStyle}>
                <span style={rankStyle}>{rank}</span>
                {Array.from({ length: 8 }, (_, file) => {
                  const square = (rank - 1) * 8 + file;
                  const piece = state.board.squares[square] ?? null;
                  const isDark = (rank + file) % 2 === 0;
                  const highlighted = square === from || square === to || square === state.fight_location;
                  return (
                    <div
                      key={square}
                      title={`${squareName(square)} ${piece ? PIECE_NAME[piece.type] : "empty"}`}
                      style={{
                        ...cellStyle,
                        background: highlighted ? "#fbbf24" : isDark ? "#202026" : "#303038",
                        boxShadow: highlighted ? "inset 0 0 0 3px #facc15" : undefined,
                      }}
                    >
                      {piece && (
                        <span
                          style={{
                            ...pieceStyle,
                            color: pieceColor(piece),
                            borderColor: pieceColor(piece),
                            opacity: piece.type === "hidden" ? 0.7 : 1,
                          }}
                        >
                          {PIECE_LABEL[piece.type]}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      <div style={actionStyle}>
        {Object.entries(actions ?? {}).map(([seat, action]) => (
          <span key={seat}>
            {seatLabel(events, Number(seat))}: {describeAction(action) ?? "none"}
          </span>
        ))}
      </div>
    </div>
  );
}

const wrapStyle: CSSProperties = {
  width: "min(92vmin, 760px)",
  aspectRatio: "1 / 1",
  display: "grid",
  gridTemplateRows: "auto auto 1fr auto",
  gap: 10,
  padding: 18,
  background: "#0a0a0b",
  color: "#e8e8ea",
  fontFamily: "ui-monospace, 'JetBrains Mono', Menlo, Consolas, monospace",
};

const hudStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 10,
};

const playerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  minWidth: 0,
  border: "1px solid",
  borderRadius: 6,
  padding: "8px 10px",
  background: "#141416",
  fontSize: 13,
};

const chipStyle: CSSProperties = {
  width: 10,
  height: 10,
  borderRadius: 2,
  flex: "0 0 auto",
};

const mutedStyle: CSSProperties = {
  marginLeft: "auto",
  color: "#8a8a92",
  fontSize: 11,
};

const statusStyle: CSSProperties = {
  display: "flex",
  justifyContent: "center",
  flexWrap: "wrap",
  gap: "8px 16px",
  color: "#cbd5e1",
  fontSize: 12,
  textTransform: "uppercase",
};

const boardWrapStyle: CSSProperties = {
  minHeight: 0,
  display: "grid",
  gridTemplateRows: "20px 1fr",
  gap: 4,
};

const filesStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "20px repeat(8, 1fr)",
  textAlign: "center",
  color: "#8a8a92",
  fontSize: 12,
};

const gridWithRanksStyle: CSSProperties = {
  display: "grid",
  gridTemplateRows: "repeat(8, 1fr)",
  gap: 2,
};

const rankRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "20px repeat(8, 1fr)",
  gap: 2,
};

const rankStyle: CSSProperties = {
  alignSelf: "center",
  justifySelf: "center",
  color: "#8a8a92",
  fontSize: 12,
};

const cellStyle: CSSProperties = {
  minWidth: 0,
  minHeight: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  borderRadius: 4,
};

const pieceStyle: CSSProperties = {
  width: "72%",
  height: "72%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  border: "2px solid",
  borderRadius: 999,
  background: "#0a0a0b",
  fontWeight: 800,
  fontSize: "clamp(12px, 3vmin, 24px)",
};

const actionStyle: CSSProperties = {
  display: "flex",
  justifyContent: "center",
  flexWrap: "wrap",
  gap: "6px 16px",
  minHeight: 18,
  color: "#8a8a92",
  fontSize: 11,
};

