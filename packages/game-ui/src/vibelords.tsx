"use client";

import { useMemo, useState } from "react";

import { VibelordsBoard } from "./vibelords/board";
import { VIBELORDS_TICKS_PER_SEC, type VibelordsState } from "./vibelords/types";
import { PlaybackControls, usePlayback } from "./controls";
import { AspectSelect, ReplayFrame, ASPECT_RATIOS, type AspectRatio } from "./frame";
import {
  seatLabel,
  type RawEvent,
  type RawGameEndEvt,
  type RawGameStartEvt,
} from "./types";

type Frame = { state: VibelordsState };

// Vibelords' board renders natively at 16:9, so that's the default replay ratio.
const VIBELORDS_NATIVE_RATIO: AspectRatio = "16:9";

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
  defaultRatio = VIBELORDS_NATIVE_RATIO,
  ratios = ASPECT_RATIOS,
}: {
  events: RawEvent[];
  // Seat the viewer played, so their HUD reads in their color.
  mySeat?: number | null;
  // Initial aspect ratio (defaults to the board's native 16:9). The selector
  // lets viewers re-frame into the other social ratios for capture.
  defaultRatio?: AspectRatio;
  ratios?: AspectRatio[];
}) {
  const frames = useMemo(() => buildVibelordsFrames(events), [events]);
  const names = useMemo(() => {
    const start = events.find((e) => e.type === "game_start") as
      | RawGameStartEvt
      | undefined;
    return start?.names ?? null;
  }, [events]);
  const [ratio, setRatio] = useState<AspectRatio>(defaultRatio);
  const totalFrames = frames.length;
  const playback = usePlayback(totalFrames, VIBELORDS_TICKS_PER_SEC);
  const current = frames[Math.min(playback.frame, Math.max(0, totalFrames - 1))];
  const finalPlacement =
    (events[events.length - 1] as RawGameEndEvt | undefined)?.placement ?? [];

  if (totalFrames === 0 || !current) {
    return <div className="vw-replay vw-replay__empty">empty replay</div>;
  }

  // The board HUD already shows per-player names/resources and the keeps show
  // HP, so the only thing the (now-dropped) sidebar added is the final result.
  // Surface that as a brand line only once playback reaches the end, so it
  // doesn't spoil the outcome mid-replay.
  const winnerSeat = finalPlacement[0];
  const atEnd = playback.frame >= totalFrames - 1;
  const brand =
    atEnd && winnerSeat !== undefined ? (
      <span className="vw-frame__result">🏆 {seatLabel(events, winnerSeat)}</span>
    ) : undefined;

  return (
    <div className="vw-replay">
      <ReplayFrame ratio={ratio} nativeRatio={VIBELORDS_NATIVE_RATIO} brand={brand}>
        <VibelordsBoard state={current.state} mySeat={mySeat} names={names} />
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
