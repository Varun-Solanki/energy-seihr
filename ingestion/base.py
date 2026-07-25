from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class SourcePayload:
    source_name: str
    source_uri: str
    local_path: Path | None = None
    content_type: str = "text/plain"
    raw_text: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class NormalizedRecord:
    source_name: str
    record_type: str
    period: str
    region: str | None
    value: float | int | str | None
    unit: str | None = None
    metadata: dict[str, Any] | None = None


class SourceClient(Protocol):
    def fetch(self, source_uri: str, local_path: Path | None = None) -> SourcePayload:
        ...

    def normalize(self, payload: SourcePayload) -> list[NormalizedRecord]:
        ...
