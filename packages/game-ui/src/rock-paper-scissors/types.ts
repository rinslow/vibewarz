export type RpsPieceType =
  | "unassigned"
  | "rock"
  | "paper"
  | "scissors"
  | "trap"
  | "flag"
  | "hidden";

export type RpsPhase = "setup" | "play" | "fight" | "end";

export type RpsPiece = {
  type: RpsPieceType;
  color: 0 | 1;
  visible_to_enemy: boolean;
};

export type RpsPlayer = {
  seat: number;
  color: 0 | 1;
  color_hex: string;
  has_committed_setup: boolean;
  setup_valid: boolean;
  fight_commit: "rock" | "paper" | "scissors" | null;
};

export type RpsState = {
  tick: number;
  phase: RpsPhase;
  dims: { w: number; h: number };
  board: { squares: (RpsPiece | null)[] };
  current_turn: 0 | 1;
  players: RpsPlayer[];
  winner: 0 | 1 | null;
  fight_location: number | null;
  fight_attacker: number | null;
  placement: number[];
};

export type RpsAction =
  | { type: "setup"; assignments: unknown[] }
  | { type: "move"; from: number; to: number; move_type?: "movement" | "capture" }
  | { type: "fight"; piece: "rock" | "paper" | "scissors" }
  | { type: "pass" };

