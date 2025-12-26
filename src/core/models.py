import numpy as np
from typing import Tuple
from dataclasses import dataclass


@dataclass
class MatchResult:
    found: bool
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class ActionSequence:
    name: str
    templates: list[np.ndarray]
    template_names: list[str]

    @property
    def action_count(self) -> int:
        return len(self.templates)
