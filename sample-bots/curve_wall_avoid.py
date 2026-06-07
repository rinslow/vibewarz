"""Turns away from arena walls when one is within K units of the projected head."""

from __future__ import annotations

import math

from vibewarz import CurveAction, CurveBot, CurveState


class WallAvoidBot(CurveBot):
    display_name = "WallAvoidBot"

    LOOKAHEAD = 80.0

    def act(self, state: CurveState):
        me = state.player(self.seat)
        if not me.alive:
            return CurveAction(turn="STRAIGHT")
        arena = state.arena
        speed = state.speed
        rad = math.radians(me.heading_deg)
        steps = max(1, int(self.LOOKAHEAD / speed))
        nx = me.x + steps * speed * math.cos(rad)
        ny = me.y + steps * speed * math.sin(rad)
        if 0 < nx < arena.w and 0 < ny < arena.h:
            return CurveAction(turn="STRAIGHT")
        cx, cy = arena.w / 2, arena.h / 2
        desired = math.degrees(math.atan2(cy - me.y, cx - me.x)) % 360.0
        diff = (desired - me.heading_deg + 540.0) % 360.0 - 180.0
        return CurveAction(turn="LEFT" if diff < 0 else "RIGHT")
