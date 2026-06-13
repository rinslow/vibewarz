"use client";

import { useMemo, useState } from "react";

import { PlaybackControls, usePlayback } from "./controls";
import { AspectSelect, ReplayFrame, ASPECT_RATIOS, type AspectRatio } from "./frame";
import { PokerBoard, type SeatInfo } from "./poker/board";
import type { PokerState } from "./poker/types";
import { seatLabel, type RawEvent, type RawGameEndEvt } from "./types";

type Frame = { state: PokerState };

// Poker is turn-based; each tick_result captures the full post-action state
// (history is delta-encoded but the renderer doesn't use it). No incremental
// reconstruction needed — replay frames are an identity map.
export function buildPokerFrames(events: RawEvent[]): Frame[] {
  const frames: Frame[] = [];
  for (const evt of events) {
    if (evt.type === "game_start" || evt.type === "tick_result") {
      frames.push({ state: evt.state as PokerState });
    }
  }
  return frames;
}

// POV: "all" reveals every seat's hole cards (omniscient spectator view —
// the default, since the journal already contains all hole cards). A seat
// number restricts to that seat's POV: their cards always visible, others
// only at showdown — matching Poker.view_for() in the OSS engine.
type Pov = "all" | number;

// Poker: tick_interval_ms=0 (event-paced, no wall-clock cadence). We pick
// 2 Hz so each action takes 500ms at 1× — fast enough to feel responsive,
// slow enough to read.
const POKER_TICKS_PER_SEC = 2;

// Poker's oval felt is laid out landscape, so the board renders natively at
// 16:9 — that's the default replay ratio. The selector re-frames into the rest.
const POKER_NATIVE_RATIO: AspectRatio = "16:9";

export function PokerReplay({
  events,
  defaultRatio = POKER_NATIVE_RATIO,
  ratios = ASPECT_RATIOS,
}: {
  events: RawEvent[];
  // Initial aspect ratio (defaults to the board's native 16:9). The selector
  // lets viewers re-frame into the other social ratios for capture.
  defaultRatio?: AspectRatio;
  ratios?: AspectRatio[];
}) {
  const frames = useMemo(() => buildPokerFrames(events), [events]);
  const totalFrames = frames.length;
  const playback = usePlayback(totalFrames, POKER_TICKS_PER_SEC);
  const current = frames[Math.min(playback.frame, Math.max(0, totalFrames - 1))];
  const finalPlacement =
    (events[events.length - 1] as RawGameEndEvt | undefined)?.placement ?? [];

  const seats = useMemo<number[]>(() => {
    const first = frames[0]?.state;
    if (!first) return [];
    return first.players.map((p) => p.seat).sort((a, b) => a - b);
  }, [frames]);

  // Real player names for the on-table seat plates (the board falls back to
  // "seat N" without this) — so identity lives on the table and the sidebar can
  // be dropped.
  const seatInfo = useMemo<SeatInfo[]>(
    () =>
      seats.map((s) => ({
        seat: s,
        handle: seatLabel(events, s),
        is_bot: false,
        bot_label: null,
      })),
    [seats, events],
  );

  const [pov, setPov] = useState<Pov>("all");
  const [ratio, setRatio] = useState<AspectRatio>(defaultRatio);

  // Apply POV redaction client-side. The journal has full info; for a chosen
  // seat we blank other seats' hole_cards until the engine sets
  // showdown_hands for that hand — mirroring Poker.view_for() in Python.
  const renderedState = useMemo<PokerState | null>(() => {
    if (!current) return null;
    if (pov === "all") return current.state;
    const showdown = current.state.showdown_hands !== null;
    return {
      ...current.state,
      players: current.state.players.map((p) =>
        p.seat === pov || showdown || !p.in_hand ? p : { ...p, hole_cards: [] },
      ),
    };
  }, [current, pov]);

  if (totalFrames === 0 || !current || !renderedState) {
    return <div className="vw-replay vw-replay__empty">empty replay</div>;
  }

  const povControl = (
    <select
      value={pov === "all" ? "all" : String(pov)}
      onChange={(e) => {
        const v = e.target.value;
        setPov(v === "all" ? "all" : parseInt(v, 10));
      }}
      title="POV — restrict visible hole cards to one seat's knowledge"
      className="vw-replay__speed"
    >
      <option value="all">POV: all</option>
      {seats.map((s) => (
        <option key={s} value={String(s)}>
          POV: seat {s}
        </option>
      ))}
    </select>
  );

  const revealAll = pov === "all";
  const povSeat = pov === "all" ? null : pov;

  // Winner shown in the brand corner only at the end, so it doesn't spoil.
  const winnerSeat = finalPlacement[0];
  const atEnd = playback.frame >= totalFrames - 1;
  const brand =
    atEnd && winnerSeat !== undefined ? (
      <span className="vw-frame__result">🏆 {seatLabel(events, winnerSeat)}</span>
    ) : undefined;

  // Off-native ratios letterbox the wide table — fill the band with a chip-count
  // leaderboard (sorted high→low, busted players dimmed). The frame renders it
  // only when a band exists, so native 16:9 stays clean.
  const leaderboard = (
    <>
      {[...renderedState.players]
        .sort((a, b) => b.stack - a.stack)
        .map((p) => {
          const out = !p.in_tournament || p.stack === 0;
          return (
            <span
              key={p.seat}
              className={"vw-frame__legend-item" + (out ? " vw-frame__legend-item--dead" : "")}
            >
              <span
                className="vw-frame__legend-chip"
                style={{ backgroundColor: p.color }}
              />
              {seatLabel(events, p.seat)} {p.stack}
            </span>
          );
        })}
    </>
  );

  return (
    <div className="vw-replay">
      <ReplayFrame
        ratio={ratio}
        nativeRatio={POKER_NATIVE_RATIO}
        brand={brand}
        // 9:16 spins the table to fill the frame (no dead band), so the
        // leaderboard only fills the 1:1 letterbox bands.
        legend={ratio === "1:1" ? leaderboard : undefined}
      >
        <PokerBoard
          state={renderedState}
          mySeat={povSeat}
          seatInfo={seatInfo}
          revealAll={revealAll}
          rotate90={ratio === "9:16"}
          emphasizeMe={false}
        />
      </ReplayFrame>
      <PlaybackControls
        totalFrames={totalFrames}
        currentTick={current.state.tick}
        maxTick={frames[totalFrames - 1].state.tick}
        playback={playback}
        extra={
          <>
            {povControl}
            <AspectSelect value={ratio} options={ratios} onChange={setRatio} />
          </>
        }
      />
    </div>
  );
}
