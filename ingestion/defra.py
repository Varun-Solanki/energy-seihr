from __future__ import annotations

from csv import DictReader
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .base import NormalizedRecord, SourcePayload


class DefraPm25Client:
    source_name = "defra_pm25"

    def fetch(self, source_uri: str, local_path: Path | None = None) -> SourcePayload:
        raw_text = self._read_or_download(source_uri, local_path)
        return SourcePayload(
            source_name=self.source_name,
            source_uri=source_uri,
            local_path=local_path,
            content_type="text/csv",
            raw_text=raw_text,
            metadata={"source_family": "defra"},
        )

    def normalize(self, payload: SourcePayload) -> list[NormalizedRecord]:
        if not payload.raw_text:
            return []
        try:
            frame = pd.read_csv(pd.io.common.StringIO(payload.raw_text))
        except Exception:
            rows = list(DictReader(payload.raw_text.splitlines()))
            frame = pd.DataFrame(rows)

        records: list[NormalizedRecord] = []
        for _, row in frame.iterrows():
            records.append(
                NormalizedRecord(
                    source_name=self.source_name,
                    record_type="pm25",
                    period=str(row.iloc[0]) if len(row) else "unknown",
                    region=str(row.iloc[1]) if len(row) > 1 else None,
                    value=self._coerce_value(row.iloc[-1]) if len(row) else None,
                    unit="ugm-3",
                    metadata={"columns": list(frame.columns)},
                )
            )
        return records

    def _read_or_download(self, source_uri: str, local_path: Path | None) -> str:
        if local_path is not None and local_path.exists():
            return local_path.read_text(encoding="utf-8")
        response = requests.get(source_uri, timeout=30)
        response.raise_for_status()
        if local_path is not None:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(response.text, encoding="utf-8")
        return response.text

    def _coerce_value(self, value: Any) -> float | str | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return str(value) if value is not None else None
