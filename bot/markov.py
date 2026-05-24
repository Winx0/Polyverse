"""
Markov Chain model for BTC price state persistence analysis.
Tracks transitions between UP/DOWN states and calculates persistence probability.
"""

import numpy as np
from collections import deque


class MarkovModel:
    """
    Builds a transition matrix from observed BTC price movements.
    States: UP (price went up), DOWN (price went down)
    """

    STATES = ["UP", "DOWN"]
    STATE_MAP = {"UP": 0, "DOWN": 1}

    def __init__(self, window_size: int = 50):
        """
        Args:
            window_size: Number of recent observations to use for transition matrix.
                         Larger = more stable, smaller = more adaptive.
        """
        self.window_size = window_size
        self.history = deque(maxlen=window_size)
        # Initialize with uniform transitions (no bias)
        self.transition_matrix = np.array([
            [0.5, 0.5],  # From UP: P(UP|UP), P(DOWN|UP)
            [0.5, 0.5],  # From DOWN: P(UP|DOWN), P(DOWN|DOWN)
        ])

    def add_observation(self, state: str):
        """Add a new state observation ('UP' or 'DOWN')."""
        if state not in self.STATES:
            raise ValueError(f"State must be one of {self.STATES}, got '{state}'")
        self.history.append(state)
        self._update_matrix()

    def _update_matrix(self):
        """Recalculate transition matrix from history."""
        if len(self.history) < 2:
            return

        counts = np.zeros((2, 2))
        for i in range(len(self.history) - 1):
            from_state = self.STATE_MAP[self.history[i]]
            to_state = self.STATE_MAP[self.history[i + 1]]
            counts[from_state][to_state] += 1

        # Normalize rows (add smoothing to avoid division by zero)
        for i in range(2):
            row_sum = counts[i].sum()
            if row_sum > 0:
                self.transition_matrix[i] = counts[i] / row_sum
            else:
                self.transition_matrix[i] = [0.5, 0.5]

    def get_persistence_probability(self, current_state: str) -> float:
        """
        Get p(j*,j*) - probability that current state persists.
        This is the diagonal element of the transition matrix.

        Args:
            current_state: Current state ('UP' or 'DOWN')

        Returns:
            Probability of staying in the same state (0.0 to 1.0)
        """
        idx = self.STATE_MAP[current_state]
        return float(self.transition_matrix[idx][idx])

    def get_current_state(self) -> str | None:
        """Get the most recent observed state."""
        if not self.history:
            return None
        return self.history[-1]

    def get_transition_matrix(self) -> dict:
        """Return human-readable transition matrix."""
        return {
            "P(UP|UP)": self.transition_matrix[0][0],
            "P(DOWN|UP)": self.transition_matrix[0][1],
            "P(UP|DOWN)": self.transition_matrix[1][0],
            "P(DOWN|DOWN)": self.transition_matrix[1][1],
        }

    def has_enough_data(self) -> bool:
        """Check if we have enough observations for reliable estimates."""
        return len(self.history) >= 10

    def reset(self):
        """Clear all history and reset matrix."""
        self.history.clear()
        self.transition_matrix = np.array([[0.5, 0.5], [0.5, 0.5]])
