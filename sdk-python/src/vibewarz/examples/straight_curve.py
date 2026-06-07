"""Trivial example bot: always go STRAIGHT.

Run:
    vibewarz play sdk-python/src/vibewarz/examples/straight_curve.py --mode practice
"""

from vibewarz import CurveAction, CurveBot, CurveState, run


class StraightBot(CurveBot):
    def act(self, state: CurveState):
        return CurveAction(turn="STRAIGHT")


if __name__ == "__main__":
    run(StraightBot(), mode="practice")
