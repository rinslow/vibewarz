// Types mirroring the Blast engine state in
// games/src/vibewarz_games/blast/game.py.

export type BlastCell = "empty" | "hard" | "soft";

export type BlastPlayer = {
  seat: number;
  x: number;
  y: number;
  alive: boolean;
  color: string;
  bombs_max: number;
  bombs_active: number;
  blast_range: number;
  move_cooldown: number;
  move_cooldown_remaining: number;
  powerup_counts: { bomb: number; range: number; speed: number };
};

export type BlastBomb = {
  x: number;
  y: number;
  timer: number;
  owner: number;
  range: number;
};

export type BlastFlame = { x: number; y: number; timer: number };

export type BlastPowerupKind = "bomb" | "range" | "speed";

export type BlastPowerup = {
  id: string;
  x: number;
  y: number;
  kind: BlastPowerupKind;
};

export type BlastState = {
  tick: number;
  dims: { w: number; h: number };
  board: BlastCell[][];
  max_ticks: number;
  shrink_start_tick: number;
  shrink_step: number;
  players: BlastPlayer[];
  bombs: BlastBomb[];
  flames: BlastFlame[];
  powerups: BlastPowerup[];
  placement: number[];
};

export type BlastAction = {
  move: "up" | "down" | "left" | "right" | "stay";
  drop_bomb: boolean;
};

// Engine constants mirrored from game.py. Only used for visual scaling
// (e.g. the bomb-fuse ring); not authoritative.
export const BOMB_FUSE_TICKS = 20;
// Engine tick interval (ms). Used to time the smooth-move CSS transition so
// player sprites glide between tiles instead of snapping.
export const TICK_INTERVAL_MS = 100;
