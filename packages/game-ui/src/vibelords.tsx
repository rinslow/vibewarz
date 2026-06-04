"use client";

import { useMemo } from "react";

import { VibelordsBoard } from "./vibelords/board";
import { AGE_NAMES, VIBELORDS_TICKS_PER_SEC, type VibelordsState } from "./vibelords/types";
import { PlaybackControls, usePlayback } from "./controls";
import {
  seatLabel,
  type RawEvent,
  type RawGameEndEvt,
  type RawGameStartEvt,
} from "./types";

type Frame = { state: VibelordsState };

// Vibelords replays carry the full state per tick (units die so the list stays
// bounded; no delta encoding), so frame reconstruction is an identity map.
export function buildVibelordsFrames(events: RawEvent[]): Frame[] {
  const frames: Frame[] = [];
  for (const evt of events) {
    if (evt.type === "game_start" || evt.type === "tick_result") {
      frames.push({ state: evt.state as VibelordsState });
    }
  }
  return frames;
}

export function VibelordsReplay({
  events,
  mySeat = null,
}: {
  events: RawEvent[];
  // Seat the viewer played, so their HUD/sidebar card reads in their color.
  mySeat?: number | null;
}) {
  const frames = useMemo(() => buildVibelordsFrames(events), [events]);
  const names = useMemo(() => {
    const start = events.find((e) => e.type === "game_start") as
      | RawGameStartEvt
      | undefined;
    return start?.names ?? null;
  }, [events]);
  const totalFrames = frames.length;
  const playback = usePlayback(totalFrames, VIBELORDS_TICKS_PER_SEC);
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
          <VibelordsBoard state={current.state} mySeat={mySeat} names={names} />
          <PlaybackControls
            totalFrames={totalFrames}
            currentTick={current.state.tick}
            maxTick={frames[totalFrames - 1].state.tick}
            playback={playback}
          />
        </div>
        <aside className="vw-replay__sidebar">
          {current.state.players.map((p) => {
            const base = current.state.bases[p.seat];
            const alive = !base || base.hp > 0;
            const finalPos = finalPlacement.indexOf(p.seat);
            const isMe = mySeat !== null && p.seat === mySeat;
            return (
              <div
                key={p.seat}
                className={"vw-replay__player" + (alive ? "" : " vw-replay__player--dead")}
                style={isMe ? { backgroundColor: `${p.color}14` } : undefined}
              >
                <div className="vw-replay__player-row">
                  <div
                    className="vw-replay__player-chip"
                    style={{ backgroundColor: p.color }}
                  />
                  <p className="vw-replay__player-name">{seatLabel(events, p.seat)}</p>
                  <span
                    className={
                      "vw-replay__player-status " +
                      (alive
                        ? "vw-replay__player-status--alive"
                        : "vw-replay__player-status--dead")
                    }
                  >
                    {alive ? "fighting" : "fallen"}
                  </span>
                </div>
                <div className="vw-replay__player-stats">
                  <span>{AGE_NAMES[p.age] ?? `age ${p.age}`}</span>
                  <span>
                    ◎<span style={{ color: "#fbbf24" }}>{Math.round(p.gold)}</span>
                  </span>
                  <span>
                    ❤<span style={{ color: "#a3e635" }}>{Math.max(0, Math.round(base?.hp ?? 0))}</span>
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
