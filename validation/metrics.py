from __future__ import annotations

import numpy as np


class Metrics:
    def mse(self, predicted: np.ndarray, actual: np.ndarray) -> float:
        return float(np.mean((predicted - actual) ** 2))
