from __future__ import annotations

from dataclasses import dataclass


def _update_grammar(grammar: str) -> str:
    expanded = ""
    for char in grammar:
        if char == "X":
            expanded += "F+[[X]-X]-F[-FX]+X"
        elif char == "F":
            expanded += "FF"
    return expanded


@dataclass(frozen=True)
class LSystemState:
    grammar: str = "X"
    time_since_last_update_ms: float = 0.0

    def advance(self, dt_ms: float, update_interval_ms: float) -> "LSystemState":
        accumulated = self.time_since_last_update_ms + dt_ms
        grammar = self.grammar

        while accumulated >= update_interval_ms:
            grammar = _update_grammar(grammar)
            accumulated -= update_interval_ms

        return LSystemState(grammar=grammar, time_since_last_update_ms=accumulated)

    @classmethod
    def initial(cls) -> "LSystemState":
        return cls()
