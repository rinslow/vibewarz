"use client";

import { useMemo, useState } from "react";

import { BlastBoard } from "./blast/board";
import type { BlastState } from "./blast/types";
import { PlaybackControls, usePlayback } from "./controls";
import { AspectSelect, ReplayFrame, ASPECT_RATIOS, type AspectRatio } from "./frame";
import { seatLabel, type RawEvent, type RawGameEndEvt } from "./types";

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

// Blast's grid is padded to a square, so the board renders natively at 1:1 —
// that's the default replay ratio. The selector re-frames into the others.
const BLAST_NATIVE_RATIO: AspectRatio = "1:1";

export function BlastReplay({
  events,
  mySeat = null,
  defaultRatio = BLAST_NATIVE_RATIO,
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
  const frames = useMemo(() => buildBlastFrames(events), [events]);
  // Per-seat display names — drawn on each living character (native 1:1) or in
  // the dead-space legend (off-native).
  const names = useMemo(() => {
    const seats = frames[0]?.state.players.map((p) => p.seat) ?? [];
    const max = seats.length ? Math.max(...seats) : -1;
    return Array.from({ length: max + 1 }, (_, seat) => seatLabel(events, seat));
  }, [events, frames]);
  const [ratio, setRatio] = useState<AspectRatio>(defaultRatio);
  const totalFrames = frames.length;
  const playback = usePlayback(totalFrames, BLAST_TICKS_PER_SEC);
  const current = frames[Math.min(playback.frame, Math.max(0, totalFrames - 1))];
  const finalPlacement =
    (events[events.length - 1] as RawGameEndEvt | undefined)?.placement ?? [];

  if (totalFrames === 0 || !current) {
    return <div className="vw-replay vw-replay__empty">empty replay</div>;
  }

  // Identity lives in-board (names ride living characters); the dropped sidebar's
  // only remaining info is the final result — surface it as a brand line, but
  // only once playback reaches the end so it doesn't spoil the outcome.
  const winnerSeat = finalPlacement[0];
  const atEnd = playback.frame >= totalFrames - 1;
  const brand =
    atEnd && winnerSeat !== undefined ? (
      <span className="vw-frame__result">🏆 {seatLabel(events, winnerSeat)}</span>
    ) : undefined;

  // In native 1:1 names ride the characters; off-native they'd crowd the board,
  // so identity moves to a roster legend in the dead-space band instead.
  const onNative = ratio === BLAST_NATIVE_RATIO;
  const legend = onNative ? undefined : (
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
        nativeRatio={BLAST_NATIVE_RATIO}
        brand={brand}
        legend={legend}
      >
        <BlastBoard
          state={current.state}
          mySeat={mySeat}
          names={names}
          showNames={onNative}
          frame
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
