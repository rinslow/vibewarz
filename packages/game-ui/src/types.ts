// Shared replay-side event types. Mirrors the Pydantic models in
// `vibewarz/protocol/replay.py` (the canonical schema). State is left opaque
// (`unknown`) here so per-game renderers can narrow to their own typed state
// shape without the dispatcher having to know about all of them.

export type RawGameStartEvt = {
  type: "game_start";
  state: unknown;
  seed: number;
  match_id: string;
  game_id?: string;
  // Optional display names keyed by seat ("0", "1", ...). Absent on replays
  // written before naming shipped — consumers fall back to seat labels.
  names?: Record<string, string>;
};

export type RawTickResultEvt = {
  type: "tick_result";
  ts?: number;
  match_id?: string;
  tick: number;
  state: unknown;
  actions?: Record<string, unknown>;
  eliminated?: number[];
};

export type RawGameEndEvt = {
  type: "game_end";
  ts?: number;
  match_id?: string;
  placement: number[];
  reason: string;
  final_state: unknown;
};

export type RawEvent = RawGameStartEvt | RawTickResultEvt | RawGameEndEvt;

export type RawReplay = {
  match_id: string;
  game_id?: string;
  events: RawEvent[];
};

// Display label for a seat: the game_start name when the replay carries one,
// else "seat N". Renderers derive this from their own `events` prop so no
// component API has to change to support named replays.
export function seatLabel(events: RawEvent[], seat: number): string {
  const start = events.find((e) => e.type === "game_start") as
    | RawGameStartEvt
    | undefined;
  return start?.names?.[String(seat)] ?? `seat ${seat}`;
}

// Inferred game id when the envelope didn't tag it (replays written before
// envelope tagging). Looks at the shape of the initial state.
export function detectGameId(replay: RawReplay): string | null {
  if (replay.game_id) return replay.game_id;
  const first = replay.events.find((e) => e.type === "game_start") as
    | RawGameStartEvt
    | undefined;
  if (first?.game_id) return first.game_id;
  const s = first?.state as Record<string, unknown> | undefined;
  if (!s) return null;
  // community_cards is uniquely Texas Hold'em / poker; `pot` would false-
  // positive against any future game that tracks a shared chip pool.
  if ("community_cards" in s) return "poker";
  if ("board" in s && "bombs" in s) return "blast";
  if ("board" in s && "current_turn" in s && "fight_location" in s) {
    return "rock-paper-scissors";
  }
  if ("trails" in s || "trail_delta" in s) return "curve";
  if ("bases" in s && "units" in s && "lane" in s) return "vibelords";
  return null;
}
