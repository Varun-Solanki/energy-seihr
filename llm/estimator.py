from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EstimatedParameters:
    values: dict[str, float]
    rationale: str


class ParameterEstimator:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def estimate(self, context: dict[str, Any]) -> EstimatedParameters:
        return EstimatedParameters(values={}, rationale="")
