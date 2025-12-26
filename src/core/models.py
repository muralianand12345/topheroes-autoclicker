from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class MatchResult:
    """Result of a template matching operation."""

    found: bool
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0

    @property
    def center(self) -> Tuple[int, int]:
        """Get center coordinates of the matched region."""
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class ActionSequence:
    """A sequence of actions to perform."""

    name: str
    templates: list[np.ndarray]
    template_names: list[str]

    @property
    def action_count(self) -> int:
        return len(self.templates)
