"""Small, data-driven state machine shared by the order, refund and dispute flows.

The transition table comes from config/commerce/state_machine.json, so adding a
state is a configuration change.  Illegal transitions raise a Conflict with the
current state and the attempted event, which is what the HTTP layer returns as
409 and what the tests assert.
"""

from __future__ import annotations

from ..core.errors import Conflict


class StateMachine:
    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.initial = str(spec["initial"])
        self.states = [str(state) for state in spec["states"]]
        self.transitions = list(spec["transitions"])
        self.terminal = [str(state) for state in spec.get("terminal", [])]

    def find(self, event: str) -> list[dict]:
        return [item for item in self.transitions if item["event"] == event]

    def target(self, state: str, event: str, actor_kind: str) -> str:
        candidates = self.find(event)
        if not candidates:
            raise Conflict(f"unknown event {event!r}")
        for item in candidates:
            if state in item["from"] and actor_kind in item["actors"]:
                return str(item["to"])
        allowed = sorted({item["to"] for item in candidates if state in item["from"]})
        if allowed:
            raise Conflict(
                f"event {event!r} is not allowed for actor {actor_kind!r} in state {state!r}"
            )
        raise Conflict(f"event {event!r} is not allowed in state {state!r}")

    def available(self, state: str) -> list[dict]:
        rows = []
        for item in self.transitions:
            if state in item["from"]:
                rows.append({"event": item["event"], "to": item["to"], "actors": list(item["actors"])})
        return rows

    def can(self, state: str, event: str, actor_kind: str = "system") -> bool:
        try:
            self.target(state, event, actor_kind)
            return True
        except Conflict:
            return False
