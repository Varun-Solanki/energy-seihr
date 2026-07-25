from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


StateVector = np.ndarray
DerivativeFn = Callable[[float, StateVector], StateVector]


@dataclass(frozen=True)
class SimulationResult:
    time: np.ndarray
    trajectory: np.ndarray


class RK4Engine:
    def integrate(self, derivative: DerivativeFn, initial_state: StateVector, time_grid: np.ndarray) -> SimulationResult:
        trajectory = np.zeros((len(time_grid), len(initial_state)), dtype=float)
        trajectory[0] = initial_state
        for index in range(1, len(time_grid)):
            t_prev = time_grid[index - 1]
            dt = time_grid[index] - t_prev
            state_prev = trajectory[index - 1]
            k1 = derivative(t_prev, state_prev)
            k2 = derivative(t_prev + dt / 2, state_prev + dt * k1 / 2)
            k3 = derivative(t_prev + dt / 2, state_prev + dt * k2 / 2)
            k4 = derivative(t_prev + dt, state_prev + dt * k3)
            trajectory[index] = state_prev + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        return SimulationResult(time=time_grid, trajectory=trajectory)
