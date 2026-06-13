"""Terminal-controlled Rock Paper Scissors bot for local play.

Run this as one seat in `vibewarz play-local` and type moves when prompted.
"""

from __future__ import annotations

from vibewarz import RockPaperScissorsBot, RockPaperScissorsState


def _sq(square: int) -> str:
    return f"{chr(ord('a') + square % 8)}{square // 8 + 1}"


def _parse_sq(text: str) -> int | None:
    text = text.strip().lower()
    if len(text) != 2 or text[0] < "a" or text[0] > "h" or text[1] < "1" or text[1] > "8":
        return None
    return (int(text[1]) - 1) * 8 + (ord(text[0]) - ord("a"))


def _piece_label(piece) -> str:
    if piece is None:
        return "."
    label = {
        "rock": "R",
        "paper": "P",
        "scissors": "S",
        "trap": "T",
        "flag": "F",
        "hidden": "?",
        "unassigned": "?",
    }.get(piece.type, "?")
    return label.lower() if piece.color == 1 else label


class RockPaperScissorsHumanBot(RockPaperScissorsBot):
    display_name = "HumanRPS"

    def _print_board(self, state: RockPaperScissorsState) -> None:
        print()
        for rank in range(8, 0, -1):
            row = []
            for file in range(8):
                row.append(_piece_label(state.piece_at((rank - 1) * 8 + file)))
            print(f"{rank}  {' '.join(row)}")
        print("   a b c d e f g h")
        print(f"phase={state.phase} tick={state.tick} turn={state.current_turn}")

    def act(self, state: RockPaperScissorsState):
        legal = self.legal_actions(state)
        if not legal:
            return {"type": "pass"}

        self._print_board(state)

        if state.phase == "setup":
            input("Press Enter to commit the default setup...")
            return legal[0]

        if state.phase == "fight":
            while True:
                choice = input("Fight commit [rock/paper/scissors]: ").strip().lower()
                if choice in {"rock", "paper", "scissors"}:
                    return {"type": "fight", "piece": choice}
                print("Invalid fight commit.")

        print("Legal moves:", ", ".join(f"{_sq(a['from'])}->{_sq(a['to'])}" for a in legal if a.get("type") == "move"))
        while True:
            raw = input("Move (example: a2 a3), or 'first': ").strip().lower()
            if raw == "first":
                return legal[0]
            parts = raw.replace("->", " ").split()
            if len(parts) != 2:
                print("Enter two squares, for example: a2 a3")
                continue
            src = _parse_sq(parts[0])
            dst = _parse_sq(parts[1])
            if src is None or dst is None:
                print("Invalid square.")
                continue
            for action in legal:
                if action.get("type") == "move" and action.get("from") == src and action.get("to") == dst:
                    return action
            print("Illegal move.")
