"""Example bot: turn away from arena walls and other curves.

If a wall is within `lookahead` units of the projected head, turn the
opposite way; otherwise go straight.
"""

import math

from vibewarz import CurveAction, CurveBot, CurveState, run


class WallAvoidBot(CurveBot):
    LOOKAHEAD = 60.0  # units

    def act(self, state: CurveState):
        me = state.player(self.seat)
        if not me.alive:
            return CurveAction(turn="STRAIGHT")
        arena = state.arena
        speed = state.speed
        rad = math.radians(me.heading_deg)
        for steps in range(1, int(self.LOOKAHEAD / speed) + 1):
            nx = me.x + steps * speed * math.cos(rad)
            ny = me.y + steps * speed * math.sin(rad)
            if nx < 0 or nx > arena.w or ny < 0 or ny > arena.h:
                # Wall close — turn toward arena centre.
                cx = arena.w / 2
                cy = arena.h / 2
                desired = math.degrees(math.atan2(cy - me.y, cx - me.x)) % 360.0
                diff = (desired - me.heading_deg + 540.0) % 360.0 - 180.0
                return CurveAction(turn="LEFT" if diff < 0 else "RIGHT"), "wall ahead"
        return CurveAction(turn="STRAIGHT")


if __name__ == "__main__":
    run(WallAvoidBot(), mode="practice", loop=5)
