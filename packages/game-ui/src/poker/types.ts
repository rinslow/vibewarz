// Types mirroring the engine state shape in
// games/src/vibewarz_games/poker/game.py. Hole cards are an empty array
// when redacted (per `view_for`); a 2-element string array when visible.

export type PokerPhase =
  | "between_hands"
  | "preflop"
  | "flop"
  | "turn"
  | "river"
  | "showdown"
  | "hand_complete"
  | "done";

export type PokerPlayer = {
  seat: number;
  stack: number;
  in_tournament: boolean;
  in_hand: boolean;
  folded: boolean;
  all_in: boolean;
  committed_round: number;
  committed_hand: number;
  hole_cards: string[]; // [] when redacted
  color: string;
  last_action: PokerAction | null;
};

export type PokerState = {
  tick: number;
  hand_number: number;
  phase: PokerPhase;
  button: number;
  small_blind: number;
  big_blind: number;
  level_idx?: number;
  community_cards: string[];
  pot: number;
  side_pots: { amount: number; eligible_seats: number[] }[];
  current_bet: number;
  min_raise: number;
  action_on: number | null;
  last_aggressor: number | null;
  players: PokerPlayer[];
  history: {
    hand: number;
    phase: string;
    seat: number;
    action: PokerAction;
  }[];
  placement: number[];
  pot_distribution: { seat: number; amount: number }[] | null;
  showdown_hands: Record<string, string> | null;
};

export type PokerAction =
  | { type: "fold" }
  | { type: "check" }
  | { type: "call" }
  | { type: "bet"; amount: number }
  | { type: "raise"; to: number };

// What the user is allowed to do right now, derived client-side from state.
export type LegalKinds = {
  canCheck: boolean;
  canCall: boolean;
  canBet: boolean;
  canRaise: boolean;
  minBet: number;       // ideal opening bet floor (= big_blind)
  minRaise: number;     // ideal raise floor (= current_bet + min_raise)
  // Lowest amount the engine will actually accept right now. For a normal
  // bet/raise this matches minBet / minRaise. For a short-stack all-in
  // (stack < big_blind, or stack + committed < min_raise) the engine still
  // allows the bet/raise *as long as it's all-in*, so the slider floor
  // collapses to maxTotal.
  effectiveFloor: number;
  maxTotal: number;     // all-in total (committed_round + stack)
  toCall: number;
};

export function legalKinds(state: PokerState, seat: number): LegalKinds {
  const me = state.players.find((p) => p.seat === seat);
  const stack = me?.stack ?? 0;
  const committed = me?.committed_round ?? 0;
  const toCall = state.current_bet - committed;
  const canCheck = toCall <= 0;
  const canCall = toCall > 0 && stack > 0;
  const canBet = state.current_bet === 0 && stack > 0;
  const canRaise = state.current_bet > 0 && stack + committed > state.current_bet;
  const minBet = state.big_blind;
  const minRaise = state.current_bet + state.min_raise;
  const maxTotal = stack + committed;
  // Short-stack rule: under-min-raise / under-BB amounts are legal *only*
  // when they're the all-in (== maxTotal). When the stack can't reach the
  // regular floor, the only legal amount is maxTotal itself.
  let effectiveFloor: number;
  if (canRaise) {
    effectiveFloor = maxTotal >= minRaise ? minRaise : maxTotal;
  } else if (canBet) {
    effectiveFloor = stack >= minBet ? minBet : maxTotal;
  } else {
    effectiveFloor = 0;
  }
  return {
    canCheck,
    canCall,
    canBet,
    canRaise,
    minBet,
    minRaise,
    effectiveFloor,
    maxTotal,
    toCall,
  };
}
