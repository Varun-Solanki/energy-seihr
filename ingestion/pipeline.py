from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import NormalizedRecord, SourcePayload
from .defra import DefraPm25Client
from .fingertips import FingertipsClient
from .national_grid import NationalGridClient


@dataclass(frozen=True)
class IngestionResult:
    payloads: list[SourcePayload]
    records: list[NormalizedRecord]
    metadata: dict[str, Any]


class IngestionPipeline:
    def __init__(self) -> None:
        self.national_grid = NationalGridClient()
        self.defra = DefraPm25Client()
        self.fingertips = FingertipsClient()

    def run(
        self,
        national_grid_uri: str,
        defra_uri: str,
        fingertips_uri: str,
        local_root: str | Path | None = None,
    ) -> IngestionResult:
        root = Path(local_root) if local_root is not None else None
        payloads = [
            self.national_grid.fetch(national_grid_uri, root / "national_grid" if root else None),
            self.defra.fetch(defra_uri, root / "defra" if root else None),
            self.fingertips.fetch(fingertips_uri, root / "fingertips" if root else None),
        ]
        records = [
            *self.national_grid.normalize(payloads[0]),
            *self.defra.normalize(payloads[1]),
            *self.fingertips.normalize(payloads[2]),
        ]
        return IngestionResult(payloads=payloads, records=records, metadata={"source_count": len(payloads), "record_count": len(records)})
