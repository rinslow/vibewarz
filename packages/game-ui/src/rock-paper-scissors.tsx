"use client";

import { useMemo, useState } from "react";

import { PlaybackControls, usePlayback } from "./controls";
import { AspectSelect, ReplayFrame, ASPECT_RATIOS, type AspectRatio } from "./frame";
import { RpsBoard } from "./rock-paper-scissors/board";
import type { RpsState } from "./rock-paper-scissors/types";
import { seatLabel, type RawEvent, type RawGameEndEvt } from "./types";

type Frame = { state: RpsState; actions?: Record<string, unknown> };

export function buildRockPaperScissorsFrames(events: RawEvent[]): Frame[] {
  const frames: Frame[] = [];
  for (const evt of events) {
    if (evt.type === "game_start") {
      frames.push({ state: evt.state as RpsState });
    } else if (evt.type === "tick_result") {
      frames.push({
        state: evt.state as RpsState,
        actions: evt.actions,
      });
    }
  }
  return frames;
}

const RPS_NATIVE_RATIO: AspectRatio = "1:1";
const RPS_TICKS_PER_SEC = 2;

export function RockPaperScissorsReplay({
  events,
  defaultRatio = RPS_NATIVE_RATIO,
  ratios = ASPECT_RATIOS,
}: {
  events: RawEvent[];
  defaultRatio?: AspectRatio;
  ratios?: AspectRatio[];
}) {
  const frames = useMemo(() => buildRockPaperScissorsFrames(events), [events]);
  const [ratio, setRatio] = useState<AspectRatio>(defaultRatio);
  const totalFrames = frames.length;
  const playback = usePlayback(totalFrames, RPS_TICKS_PER_SEC);
  const current = frames[Math.min(playback.frame, Math.max(0, totalFrames - 1))];
  const finalPlacement =
    (events[events.length - 1] as RawGameEndEvt | undefined)?.placement ?? [];

  if (totalFrames === 0 || !current) {
    return <div className="vw-replay vw-replay__empty">empty replay</div>;
  }

  const winnerSeat = finalPlacement[0] ?? current.state.winner;
  const atEnd = playback.frame >= totalFrames - 1;
  const brand =
    atEnd && winnerSeat !== undefined && winnerSeat !== null ? (
      <span className="vw-frame__result">winner {seatLabel(events, winnerSeat)}</span>
    ) : undefined;

  const legend =
    ratio === RPS_NATIVE_RATIO ? undefined : (
      <>
        {current.state.players.map((p) => (
          <span key={p.seat} className="vw-frame__legend-item">
            <span
              className="vw-frame__legend-chip"
              style={{ backgroundColor: p.color_hex }}
            />
            {seatLabel(events, p.seat)}
          </span>
        ))}
      </>
    );

  return (
    <div className="vw-replay">
      <ReplayFrame
        ratio={ratio}
        nativeRatio={RPS_NATIVE_RATIO}
        brand={brand}
        legend={legend}
      >
        <RpsBoard state={current.state} events={events} actions={current.actions} />
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

