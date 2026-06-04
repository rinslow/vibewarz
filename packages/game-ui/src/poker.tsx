"use client";

import { useMemo, useState } from "react";

import { PlaybackControls, usePlayback } from "./controls";
import { PokerBoard } from "./poker/board";
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

export function PokerReplay({ events }: { events: RawEvent[] }) {
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

  const [pov, setPov] = useState<Pov>("all");

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

  return (
    <div className="vw-replay">
      <div className="vw-replay__layout">
        <div>
          <PokerBoard state={renderedState} mySeat={povSeat} revealAll={revealAll} />
          <PlaybackControls
            totalFrames={totalFrames}
            currentTick={current.state.tick}
            maxTick={frames[totalFrames - 1].state.tick}
            playback={playback}
            extra={povControl}
          />
        </div>
        <aside className="vw-replay__sidebar">
          <div className="vw-poker__info">
            <div className="vw-poker__info-row">
              <span>hand</span>
              <span>#{current.state.hand_number}</span>
            </div>
            <div className="vw-poker__info-row">
              <span>phase</span>
              <span>{current.state.phase}</span>
            </div>
            <div className="vw-poker__info-row">
              <span>pot</span>
              <span>{current.state.pot}</span>
            </div>
            <div className="vw-poker__info-row">
              <span>blinds</span>
              <span>
                {current.state.small_blind}/{current.state.big_blind}
              </span>
            </div>
          </div>
          {renderedState.players.map((p) => {
            const finalPos = finalPlacement.indexOf(p.seat);
            return (
              <div
                key={p.seat}
                className={
                  "vw-replay__player" +
                  (p.in_tournament ? "" : " vw-replay__player--dead")
                }
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
                      (p.in_tournament
                        ? "vw-replay__player-status--alive"
                        : "vw-replay__player-status--dead")
                    }
                  >
                    {p.in_tournament ? "in" : "out"}
                  </span>
                </div>
                <p className="vw-replay__player-finish">stack {p.stack}</p>
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
