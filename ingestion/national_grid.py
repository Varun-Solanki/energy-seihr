from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from .base import NormalizedRecord, SourcePayload


class NationalGridClient:
    source_name = "national_grid_carbon_intensity"

    def fetch(self, source_uri: str, local_path: Path | None = None) -> SourcePayload:
        raw_text = self._read_or_download(source_uri, local_path)
        return SourcePayload(
            source_name=self.source_name,
            source_uri=source_uri,
            local_path=local_path,
            content_type="application/json",
            raw_text=raw_text,
            metadata={"source_family": "national_grid"},
        )

    def normalize(self, payload: SourcePayload) -> list[NormalizedRecord]:
        if not payload.raw_text:
            return []

        try:
            document = json.loads(payload.raw_text)
        except json.JSONDecodeError:
            return [
                NormalizedRecord(
                    source_name=self.source_name,
                    record_type="raw_text_preview",
                    period="unknown",
                    region=None,
                    value=None,
                    unit=None,
                    metadata={"preview": payload.raw_text[:500]},
                )
            ]

        records: list[NormalizedRecord] = []
        data_block = document.get("data", []) if isinstance(document, dict) else []
        for item in data_block:
            if not isinstance(item, dict):
                continue
            period = f"{item.get('from', 'unknown')}->{item.get('to', 'unknown')}"
            if "intensity" in item:
                intensity = item.get("intensity") or {}
                records.append(
                    NormalizedRecord(
                        source_name=self.source_name,
                        record_type="intensity",
                        period=period,
                        region=item.get("region") or item.get("shortname"),
                        value=intensity.get("actual", intensity.get("forecast")),
                        unit="gco2_per_kwh",
                        metadata={"index": intensity.get("index"), "forecast": intensity.get("forecast"), "actual": intensity.get("actual")},
                    )
                )
            if "generationmix" in item:
                for fuel_row in item.get("generationmix", []):
                    if not isinstance(fuel_row, dict):
                        continue
                    records.append(
                        NormalizedRecord(
                            source_name=self.source_name,
                            record_type="generation_mix",
                            period=period,
                            region=item.get("region") or item.get("shortname"),
                            value=self._coerce_number(fuel_row.get("perc")),
                            unit="percent",
                            metadata={"fuel": fuel_row.get("fuel")},
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

    def _coerce_number(self, value: Any) -> float | int | str | None:
        try:
            number = float(value)
            return int(number) if number.is_integer() else number
        except (TypeError, ValueError):
            return str(value) if value is not None else None
