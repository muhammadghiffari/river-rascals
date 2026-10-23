"""Monotonic checkpoint tracking along river distance `s`."""
from __future__ import annotations

from collections.abc import Sequence


class CheckpointTracker:
    def __init__(self, checkpoint_s: Sequence[float]) -> None:
        self.checkpoints = sorted(float(c) for c in checkpoint_s)
        self.reached = 0

    def update(self, s: float) -> list[int]:
        """Return indices of checkpoints newly reached. Never goes backwards."""
        new: list[int] = []
        while self.reached < len(self.checkpoints) and s >= self.checkpoints[self.reached]:
            new.append(self.reached)
            self.reached += 1
        return new

    @property
    def last_checkpoint_s(self) -> float:
        return self.checkpoints[self.reached - 1] if self.reached else 0.0

    @property
    def finished(self) -> bool:
        return self.reached >= len(self.checkpoints) > 0
