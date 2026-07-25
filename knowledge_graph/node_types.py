from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

NodeKind = Literal["Region", "PowerPlant", "PolicyEvent", "EnergyEvent", "PollutionEvent", "HealthEvent", "TimePeriod", "Record"]
EdgeKind = Literal["TRIGGERED", "PRECEDED", "DOWNWIND_OF", "LOCATED_IN", "DERIVED_FROM"]


@dataclass(frozen=True)
class NodeRecord:
    id: str
    kind: NodeKind
    label: str
    properties: dict[str, Any] | None = None


@dataclass(frozen=True)
class EdgeRecord:
    source: str
    target: str
    kind: EdgeKind
    properties: dict[str, Any] | None = None
