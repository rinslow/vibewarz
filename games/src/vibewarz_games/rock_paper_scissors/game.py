"""Rock Paper Scissors — ICQ-style hidden-piece board game.

Two players secretly arrange sixteen pieces on their two home ranks of an 8x8
board: one flag, one trap, and fourteen rock/paper/scissors pieces in any mix.
Players then alternate moving one orthogonal square. Attacking an enemy piece
resolves by rock-paper-scissors, with two special defenders: traps defeat any
attacker, and flags lose immediately. Equal piece types trigger a hidden RPS
fight where both players commit rock/paper/scissors until someone wins.

The implementation mirrors the TypeScript rules supplied for the game while
adapting them to vibewarz's pure ``Game.step(state, actions)`` contract.
"""

from __future__ import annotations

from typing import Final, Literal

from .._core.base import Game, GameMeta, StepResult
from .._core.registry import register

RED: Final = 0
BLUE: Final = 1
PLAYER_COLORS: Final = ("#f43f5e", "#38bdf8")

BOARD_SIZE: Final = 8
NUM_SQUARES: Final = BOARD_SIZE * BOARD_SIZE
MAX_TICKS: Final = 1_000

PIECE_TYPES: Final = ("unassigned", "rock", "paper", "scissors", "trap", "flag")
SETUP_PIECE_TYPES: Final = ("rock", "paper", "scissors", "trap", "flag")
FIGHT_COMMITS: Final = ("rock", "paper", "scissors")
MOVE_TYPES: Final = ("movement", "capture")

PieceType = Literal["unassigned", "rock", "paper", "scissors", "trap", "flag"]
CombatResult = Literal["attacker_wins", "defender_wins", "draw"]


class Direction:
    NORTH: Final = 8
    EAST: Final = 1
    SOUTH: Final = -NORTH
    WEST: Final = -EAST

    ALL: Final = (NORTH, EAST, SOUTH, WEST)


COMBAT_RESULTS: Final[dict[str, dict[str, CombatResult]]] = {
    "rock": {"scissors": "attacker_wins", "paper": "defender_wins", "rock": "draw"},
    "paper": {"rock": "attacker_wins", "scissors": "defender_wins", "paper": "draw"},
    "scissors": {"paper": "attacker_wins", "rock": "defender_wins", "scissors": "draw"},
    "trap": {},
    "flag": {},
    "unassigned": {},
}

TIMEOUT_PIECE_VALUES: Final = {
    "flag": 20,
    "trap": 3,
    "rock": 1,
    "paper": 1,
    "scissors": 1,
    "unassigned": 0,
}


def from_rank_and_file(rank: int, file: int) -> int:
    return (rank << 3) + file


def from_algebraic(notation: str) -> int:
    if len(notation) != 2:
        raise ValueError(f"Invalid square notation: {notation}")
    file_chr = notation[0].lower()
    if file_chr < "a" or file_chr > "h":
        raise ValueError(f"Invalid file: {file_chr}")
    try:
        rank = int(notation[1])
    except ValueError as exc:
        raise ValueError(f"Invalid rank: {notation[1]}") from exc
    if rank < 1 or rank > 8:
        raise ValueError(f"Invalid rank: {rank}")
    return (rank - 1) * BOARD_SIZE + (ord(file_chr) - ord("a"))


def _is_valid_square(square: int) -> bool:
    return 0 <= square < NUM_SQUARES


def _crosses_file_boundary(from_square: int, to_square: int) -> bool:
    from_file = from_square % BOARD_SIZE
    to_file = to_square % BOARD_SIZE
    delta = to_square - from_square
    if delta == Direction.EAST and to_file <= from_file:
        return True
    if delta == Direction.WEST and to_file >= from_file:
        return True
    return False


def _setup_bounds(player_color: int) -> tuple[int, int]:
    return (0, 16) if player_color == RED else (48, 64)


def _enemy_color(player_color: int) -> int:
    return BLUE if player_color == RED else RED


def _player_idx(player_color: int) -> int:
    return 0 if player_color == RED else 1


def _piece(piece_type: str, color: int, *, visible_to_enemy: bool = False) -> dict:
    return {
        "type": piece_type,
        "color": color,
        "visible_to_enemy": visible_to_enemy,
    }


def _copy_piece(piece: dict | None) -> dict | None:
    return None if piece is None else dict(piece)


def _copy_state(state: dict) -> dict:
    return {
        **state,
        "board": {
            **state["board"],
            "squares": [_copy_piece(piece) for piece in state["board"]["squares"]],
        },
        "players": [dict(player) for player in state["players"]],
        "placement": list(state.get("placement") or []),
    }


def _initial_board() -> dict:
    squares: list[dict | None] = [None] * NUM_SQUARES
    for square in range(0, 16):
        squares[square] = _piece("unassigned", RED)
    for square in range(48, 64):
        squares[square] = _piece("unassigned", BLUE)
    return {"squares": squares}


def _default_setup(player_color: int) -> dict:
    start, end = _setup_bounds(player_color)
    squares = list(range(start, end))
    if player_color == BLUE:
        # Put the blue flag on the back edge from blue's point of view.
        squares = list(reversed(squares))
    piece_order = (
        "flag",
        "trap",
        "rock",
        "paper",
        "scissors",
        "rock",
        "paper",
        "scissors",
        "rock",
        "paper",
        "scissors",
        "rock",
        "paper",
        "scissors",
        "rock",
        "paper",
    )
    return {
        "type": "setup",
        "assignments": [
            {"square": square, "piece": {"type": piece_type, "color": player_color}}
            for square, piece_type in zip(squares, piece_order, strict=True)
        ],
    }


def get_legal_moves_of_piece(board: dict, piece_location: int) -> list[dict]:
    squares = board["squares"]
    piece = squares[piece_location]
    if piece is None:
        return []
    if piece["type"] == "trap":
        return []

    legal_moves: list[dict] = []
    for direction in Direction.ALL:
        target_square = piece_location + direction
        if (
            not _is_valid_square(target_square)
            or _crosses_file_boundary(piece_location, target_square)
        ):
            continue

        target_piece = squares[target_square]
        if target_piece is None:
            legal_moves.append(
                {"type": "move", "from": piece_location, "to": target_square, "move_type": "movement"}
            )
        elif target_piece["color"] != piece["color"]:
            legal_moves.append(
                {"type": "move", "from": piece_location, "to": target_square, "move_type": "capture"}
            )
    return legal_moves


def get_legal_moves(board: dict, player_color: int) -> list[dict]:
    all_legal_moves: list[dict] = []
    for square, piece in enumerate(board["squares"]):
        if piece is None or piece["color"] != player_color:
            continue
        all_legal_moves.extend(get_legal_moves_of_piece(board, square))
    return all_legal_moves


def determine_combat_result(attacker: dict, defender: dict) -> CombatResult:
    if defender["type"] == "trap":
        return "defender_wins"
    if defender["type"] == "flag":
        return "attacker_wins"
    return COMBAT_RESULTS.get(attacker["type"], {}).get(defender["type"], "defender_wins")


def is_winning_fight_commit(move1: str | None, move2: str | None) -> bool:
    if not move1 or not move2:
        return False
    return (
        (move1 == "rock" and move2 == "scissors")
        or (move1 == "scissors" and move2 == "paper")
        or (move1 == "paper" and move2 == "rock")
    )


@register
class RockPaperScissors(Game):
    meta = GameMeta(
        id="rock-paper-scissors",
        display_name="Rock Paper Scissors",
        min_players=2,
        max_players=2,
        tick_deadline_ms=15_000,
        tick_interval_ms=0,
        max_ticks=MAX_TICKS,
        match_wait_ms=0,
        description=(
            "ICQ-style hidden-piece duel. Arrange rocks, papers, scissors, a "
            "trap, and a flag, then out-scout and capture the enemy flag."
        ),
    )

    def initial_state(self, seed: int, num_players: int) -> dict:
        if num_players != 2:
            raise ValueError(f"Rock Paper Scissors is heads-up (2 players), got {num_players}")
        return {
            "tick": 0,
            "seed": seed,
            "phase": "setup",
            "dims": {"w": BOARD_SIZE, "h": BOARD_SIZE},
            "board": _initial_board(),
            "current_turn": RED,
            "players": [
                {
                    "seat": RED,
                    "color": RED,
                    "color_hex": PLAYER_COLORS[RED],
                    "has_committed_setup": False,
                    "setup_valid": False,
                    "fight_commit": None,
                },
                {
                    "seat": BLUE,
                    "color": BLUE,
                    "color_hex": PLAYER_COLORS[BLUE],
                    "has_committed_setup": False,
                    "setup_valid": False,
                    "fight_commit": None,
                },
            ],
            "winner": None,
            "fight_location": None,
            "fight_attacker": None,
            "placement": [],
        }

    def alive_seats(self, state: dict) -> list[int]:
        if state.get("phase") == "end":
            winner = state.get("winner")
            if winner is None:
                return []
            return [winner]
        return [RED, BLUE]

    def acting_seats(self, state: dict) -> list[int]:
        phase = state.get("phase")
        if phase == "setup":
            return [
                p["seat"]
                for p in state["players"]
                if not (p["has_committed_setup"] and p["setup_valid"])
            ]
        if phase == "play":
            return [state["current_turn"]]
        if phase == "fight":
            return [p["seat"] for p in state["players"] if p.get("fight_commit") is None]
        return []

    def view_for(self, state: dict, seat: int) -> dict:
        view = _copy_state({k: v for k, v in state.items() if k != "seed"})
        for i, piece in enumerate(view["board"]["squares"]):
            if piece is None or piece["color"] == seat:
                continue
            if piece.get("visible_to_enemy"):
                continue
            view["board"]["squares"][i] = {
                "type": "hidden",
                "color": piece["color"],
                "visible_to_enemy": False,
            }
        for player in view["players"]:
            if player["seat"] != seat:
                player["fight_commit"] = None
        return view

    def legal_actions(self, state: dict, seat: int) -> list[dict]:
        if seat not in (RED, BLUE):
            return []
        phase = state.get("phase")
        if phase == "setup":
            player = state["players"][_player_idx(seat)]
            if player["has_committed_setup"] and player["setup_valid"]:
                return []
            return [_default_setup(seat)]
        if phase == "play":
            if state["current_turn"] != seat:
                return []
            moves = get_legal_moves(state["board"], seat)
            return moves or [{"type": "pass"}]
        if phase == "fight":
            player = state["players"][_player_idx(seat)]
            if player.get("fight_commit") is not None:
                return []
            return [{"type": "fight", "piece": piece_type} for piece_type in FIGHT_COMMITS]
        return []

    def is_legal(self, state: dict, seat: int, action: dict) -> bool:
        if not isinstance(action, dict) or seat not in (RED, BLUE):
            return False
        phase = state.get("phase")
        if phase == "setup":
            player = state["players"][_player_idx(seat)]
            if player["has_committed_setup"] and player["setup_valid"]:
                return False
            return action.get("type") == "setup" and _setup_is_valid_action(state, seat, action)
        if phase == "play":
            if state["current_turn"] != seat:
                return False
            legal_moves = get_legal_moves(state["board"], seat)
            if action.get("type") == "pass":
                return not legal_moves
            if action.get("type") != "move":
                return False
            from_square = _action_from_square(action)
            to_square = action.get("to", action.get("target"))
            if not isinstance(from_square, int) or not isinstance(to_square, int):
                return False
            for move in legal_moves:
                if move["from"] == from_square and move["to"] == to_square:
                    move_type = action.get("move_type")
                    return move_type in (None, move["move_type"])
            return False
        if phase == "fight":
            player = state["players"][_player_idx(seat)]
            if player.get("fight_commit") is not None:
                return False
            return action.get("type") == "fight" and action.get("piece") in FIGHT_COMMITS
        return False

    def default_action(self, state: dict, seat: int) -> dict:
        phase = state.get("phase")
        if phase == "setup":
            return _default_setup(seat)
        if phase == "fight":
            return {"type": "fight", "piece": "rock"}
        if phase == "play":
            legal = get_legal_moves(state["board"], seat)
            return legal[0] if legal else {"type": "pass"}
        return {"type": "noop"}

    def step(self, state: dict, actions: dict[int, dict]) -> StepResult:
        phase = state.get("phase")
        if phase == "setup":
            return self._step_setup(state, actions)
        if phase == "play":
            return self._step_play(state, actions)
        if phase == "fight":
            return self._step_fight(state, actions)
        return StepResult(
            state=state,
            done=True,
            placement=list(state.get("placement") or []),
            reason="flag_captured" if state.get("winner") is not None else "done",
        )

    def _step_setup(self, state: dict, actions: dict[int, dict]) -> StepResult:
        new_state = _copy_state(state)
        for seat in self.acting_seats(state):
            action = actions.get(seat) or self.default_action(state, seat)
            if not self.is_legal(state, seat, action):
                action = self.default_action(state, seat)
            self._commit_setup(new_state, seat, action)

        players = new_state["players"]
        if all(p["has_committed_setup"] and p["setup_valid"] for p in players):
            new_state["phase"] = "play"

        return self._finish_step(new_state)

    def _commit_setup(self, state: dict, player_color: int, action: dict) -> None:
        squares = state["board"]["squares"]
        start, end = _setup_bounds(player_color)
        for square in range(start, end):
            squares[square] = None
        for assignment in action.get("assignments", []):
            square = assignment["square"]
            raw_piece = assignment["piece"]
            squares[square] = _piece(raw_piece["type"], player_color, visible_to_enemy=False)

        valid = _validate_setup(state["board"], player_color)
        player = state["players"][_player_idx(player_color)]
        player["has_committed_setup"] = True
        player["setup_valid"] = valid

    def _step_play(self, state: dict, actions: dict[int, dict]) -> StepResult:
        actor = state["current_turn"]
        legal_moves = get_legal_moves(state["board"], actor)
        if not legal_moves:
            new_state = _copy_state(state)
            self._set_winner(new_state, _enemy_color(actor), "no_legal_moves")
            return self._finish_step(new_state, done=True, reason="no_legal_moves")

        action = actions.get(actor) or self.default_action(state, actor)
        if not self.is_legal(state, actor, action):
            action = self.default_action(state, actor)

        new_state = _copy_state(state)
        from_square = _action_from_square(action)
        to_square = action.get("to", action.get("target"))
        move = next(
            move
            for move in legal_moves
            if move["from"] == from_square and move["to"] == to_square
        )
        if move["move_type"] == "movement":
            self._handle_movement(new_state, move)
            return self._finish_step(new_state)
        self._handle_capture(new_state, move)
        return self._finish_step(
            new_state,
            done=new_state["phase"] == "end",
            reason="flag_captured" if new_state["phase"] == "end" else None,
        )

    def _handle_movement(self, state: dict, move: dict) -> None:
        squares = state["board"]["squares"]
        squares[move["to"]] = squares[move["from"]]
        squares[move["from"]] = None
        self._switch_turns(state)

    def _handle_capture(self, state: dict, move: dict) -> None:
        squares = state["board"]["squares"]
        attacker = squares[move["from"]]
        defender = squares[move["to"]]
        if attacker is None or defender is None:
            return

        if defender["type"] == "flag":
            squares[move["to"]] = attacker
            squares[move["from"]] = None
            self._set_winner(state, attacker["color"], "flag_captured")
            return

        result = determine_combat_result(attacker, defender)
        if result == "attacker_wins":
            attacker["visible_to_enemy"] = True
            squares[move["to"]] = attacker
            squares[move["from"]] = None
            self._switch_turns(state)
        elif result == "defender_wins":
            defender["visible_to_enemy"] = True
            squares[move["from"]] = None
            self._switch_turns(state)
        else:
            state["phase"] = "fight"
            state["fight_location"] = move["to"]
            state["fight_attacker"] = move["from"]
            self._reset_fight_commits(state)

    def _step_fight(self, state: dict, actions: dict[int, dict]) -> StepResult:
        new_state = _copy_state(state)
        for seat in self.acting_seats(state):
            action = actions.get(seat) or self.default_action(state, seat)
            if not self.is_legal(state, seat, action):
                action = self.default_action(state, seat)
            new_state["players"][_player_idx(seat)]["fight_commit"] = action["piece"]

        red_commit = new_state["players"][_player_idx(RED)]["fight_commit"]
        blue_commit = new_state["players"][_player_idx(BLUE)]["fight_commit"]
        if red_commit and blue_commit:
            if red_commit == blue_commit:
                self._reset_fight_commits(new_state)
            else:
                self._resolve_fight(new_state, red_commit, blue_commit)

        return self._finish_step(new_state)

    def _resolve_fight(self, state: dict, red_commit: str, blue_commit: str) -> None:
        fight_location = state["fight_location"]
        fight_attacker = state["fight_attacker"]
        squares = state["board"]["squares"]
        if not isinstance(fight_location, int) or not isinstance(fight_attacker, int):
            self._reset_fight_state(state)
            state["phase"] = "play"
            return

        defender = squares[fight_location]
        attacker = squares[fight_attacker]
        if attacker is None or defender is None:
            self._reset_fight_state(state)
            state["phase"] = "play"
            return

        red_wins = is_winning_fight_commit(red_commit, blue_commit)
        attacker_wins = (
            (red_wins and attacker["color"] == RED)
            or (not red_wins and attacker["color"] == BLUE)
        )
        if attacker_wins:
            attacker["visible_to_enemy"] = True
            squares[fight_location] = attacker
            squares[fight_attacker] = None
        else:
            defender["visible_to_enemy"] = True
            squares[fight_attacker] = None

        self._reset_fight_state(state)
        state["phase"] = "play"
        self._switch_turns(state)

    def _switch_turns(self, state: dict) -> None:
        state["current_turn"] = BLUE if state["current_turn"] == RED else RED

    def _reset_fight_commits(self, state: dict) -> None:
        for player in state["players"]:
            player["fight_commit"] = None

    def _reset_fight_state(self, state: dict) -> None:
        state["fight_location"] = None
        state["fight_attacker"] = None
        self._reset_fight_commits(state)

    def _set_winner(self, state: dict, winner: int, reason: str) -> None:
        state["phase"] = "end"
        state["winner"] = winner
        state["placement"] = [winner, _enemy_color(winner)]
        state["end_reason"] = reason

    def _finish_step(
        self,
        state: dict,
        *,
        done: bool = False,
        reason: str | None = None,
    ) -> StepResult:
        state["tick"] += 1
        if state["phase"] != "end" and state["tick"] >= self.meta.max_ticks:
            placement = _timeout_placement(state)
            state["phase"] = "end"
            state["winner"] = placement[0]
            state["placement"] = placement
            state["end_reason"] = "timeout"
            done = True
            reason = "timeout"
        elif state["phase"] == "end":
            done = True
            reason = reason or state.get("end_reason") or "done"
        return StepResult(
            state=state,
            done=done,
            placement=list(state["placement"]) if done else None,
            reason=reason,
            eliminated_this_tick=tuple([] if not done else [_enemy_color(state["winner"])]),
        )

    def render_ascii(self, state: dict) -> str:
        symbols = {
            None: ".",
            "unassigned": "?",
            "rock": "R",
            "paper": "P",
            "scissors": "S",
            "trap": "T",
            "flag": "F",
        }
        rows = []
        squares = state["board"]["squares"]
        for rank in range(BOARD_SIZE - 1, -1, -1):
            cells = []
            for file in range(BOARD_SIZE):
                piece = squares[from_rank_and_file(rank, file)]
                if piece is None:
                    cells.append(".")
                    continue
                sym = symbols.get(piece["type"], "?")
                cells.append(sym.lower() if piece["color"] == BLUE else sym)
            rows.append(" ".join(cells))
        return "\n".join(rows)


def _action_from_square(action: dict) -> int | None:
    value = action.get("from", action.get("from_square", action.get("source")))
    return value if isinstance(value, int) else None


def _setup_is_valid_action(state: dict, player_color: int, action: dict) -> bool:
    assignments = action.get("assignments")
    if not isinstance(assignments, list):
        return False
    start, end = _setup_bounds(player_color)
    temp_state = _copy_state(state)
    squares = temp_state["board"]["squares"]
    for square in range(start, end):
        squares[square] = None

    for assignment in assignments:
        if not isinstance(assignment, dict):
            return False
        square = assignment.get("square")
        raw_piece = assignment.get("piece")
        if not isinstance(square, int) or square < start or square >= end:
            return False
        if not isinstance(raw_piece, dict):
            return False
        if raw_piece.get("color") != player_color:
            return False
        piece_type = raw_piece.get("type")
        if piece_type not in SETUP_PIECE_TYPES:
            return False
        squares[square] = _piece(piece_type, player_color)

    return _validate_setup(temp_state["board"], player_color)


def _validate_setup(board: dict, player_color: int) -> bool:
    squares = board["squares"]
    flag_count = 0
    trap_count = 0
    unassigned_count = 0
    start, end = _setup_bounds(player_color)
    for square in range(start, end):
        piece = squares[square]
        if piece is None:
            return False
        if piece["color"] != player_color:
            return False
        if piece["type"] == "flag":
            flag_count += 1
        elif piece["type"] == "trap":
            trap_count += 1
        elif piece["type"] == "unassigned":
            unassigned_count += 1

    for square in range(16, 48):
        piece = squares[square]
        if piece is not None and piece["color"] == player_color:
            return False

    enemy_start, enemy_end = _setup_bounds(_enemy_color(player_color))
    for square in range(enemy_start, enemy_end):
        piece = squares[square]
        if piece is not None and piece["color"] == player_color:
            return False

    return flag_count == 1 and trap_count == 1 and unassigned_count == 0


def _timeout_placement(state: dict) -> list[int]:
    scores = {RED: 0, BLUE: 0}
    for piece in state["board"]["squares"]:
        if piece is None:
            continue
        scores[piece["color"]] += TIMEOUT_PIECE_VALUES.get(piece["type"], 0)
    if scores[RED] == scores[BLUE]:
        return [RED, BLUE]
    return [RED, BLUE] if scores[RED] > scores[BLUE] else [BLUE, RED]
