"use client";

import { useMemo } from "react";

import { BlastBoard } from "./blast/board";
import type { BlastState } from "./blast/types";
import { PlaybackControls, usePlayback } from "./controls";
import type { RawEvent, RawGameEndEvt } from "./types";

type Frame = { state: BlastState };

// Blast replays carry the full mutated board/bombs/flames per tick (the
// state is bounded by the fixed board, so there's no delta encoding), so
// frame reconstruction is just an identity map over the events' states.
export function buildBlastFrames(events: RawEvent[]): Frame[] {
  const frames: Frame[] = [];
  for (const evt of events) {
    if (evt.type === "game_start" || evt.type === "tick_result") {
      frames.push({ state: evt.state as BlastState });
    }
  }
  return frames;
}

// Blast: tick_interval_ms=100 → 10 Hz live cadence.
const BLAST_TICKS_PER_SEC = 10;

export function BlastReplay({
  events,
  mySeat = null,
}: {
  events: RawEvent[];
  // Seat the viewer played, so their row/character read in their own seat
  // color. null → neutral spectator view (no highlight).
  mySeat?: number | null;
}) {
  const frames = useMemo(() => buildBlastFrames(events), [events]);
  const totalFrames = frames.length;
  const playback = usePlayback(totalFrames, BLAST_TICKS_PER_SEC);
  const current = frames[Math.min(playback.frame, Math.max(0, totalFrames - 1))];
  const finalPlacement =
    (events[events.length - 1] as RawGameEndEvt | undefined)?.placement ?? [];

  if (totalFrames === 0 || !current) {
    return <div className="vw-replay vw-replay__empty">empty replay</div>;
  }

  return (
    <div className="vw-replay">
      <div className="vw-replay__layout">
        <div>
          <BlastBoard state={current.state} mySeat={mySeat} />
          <PlaybackControls
            totalFrames={totalFrames}
            currentTick={current.state.tick}
            maxTick={frames[totalFrames - 1].state.tick}
            playback={playback}
          />
        </div>
        <aside className="vw-replay__sidebar">
          {current.state.players.map((p) => {
            const finalPos = finalPlacement.indexOf(p.seat);
            const isMe = mySeat !== null && p.seat === mySeat;
            return (
              <div
                key={p.seat}
                className={
                  "vw-replay__player" +
                  (p.alive ? "" : " vw-replay__player--dead")
                }
                // Your own row is tinted with your seat color — identifies you
                // by color alone, matching your character on the board.
                style={isMe ? { backgroundColor: `${p.color}14` } : undefined}
              >
                <div className="vw-replay__player-row">
                  <div
                    className="vw-replay__player-chip"
                    style={{ backgroundColor: p.color }}
                  />
                  <p className="vw-replay__player-name">seat {p.seat}</p>
                  <span
                    className={
                      "vw-replay__player-status " +
                      (p.alive
                        ? "vw-replay__player-status--alive"
                        : "vw-replay__player-status--dead")
                    }
                  >
                    {p.alive ? "alive" : "dead"}
                  </span>
                </div>
                <div className="vw-replay__player-stats">
                  <span>
                    B<span style={{ color: "#a3e635" }}>{p.bombs_max}</span>
                  </span>
                  <span>
                    R<span style={{ color: "#fbbf24" }}>{p.blast_range}</span>
                  </span>
                </div>
                {finalPos >= 0 && (
                  <p className="vw-replay__player-finish">final: #{finalPos + 1}</p>
                )}
              </div>
            );
          })}
        </aside>
      </div>
    </div>
  );
}
