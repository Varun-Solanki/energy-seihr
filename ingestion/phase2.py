from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
import requests

from config.settings import BASE_DIR
from config.source_registry import SourceDefinition, SourceRegistry

from .base import NormalizedRecord, SourcePayload


class UniversalIngestor(Protocol):
    def fetch(self, source: SourceDefinition) -> SourcePayload:
        ...

    def normalize(self, payload: SourcePayload) -> list[NormalizedRecord]:
        ...


@dataclass(frozen=True)
class UniversalIngestionResult:
    payloads: list[SourcePayload]
    records: list[NormalizedRecord]
    skipped_sources: list[str]


class RegistryIngestionPipeline:
    def __init__(
        self,
        registry: SourceRegistry,
        output_dir: Path | None = None,
        include_live_apis: bool = False,
    ) -> None:
        self.registry = registry
        self.output_dir = output_dir or BASE_DIR / "data" / "processed"
        self.include_live_apis = include_live_apis

    def run_country(self, country_iso3: str) -> UniversalIngestionResult:
        payloads: list[SourcePayload] = []
        records: list[NormalizedRecord] = []
        skipped: list[str] = []

        for source in self.registry.sources_for_country(country_iso3):
            if source.is_api and not self.include_live_apis:
                skipped.append(f"{source.id}: live API skipped")
                continue
            ingestor = build_ingestor(source, target_country_iso3=country_iso3)
            payload = ingestor.fetch(source)
            payloads.append(payload)
            records.extend(ingestor.normalize(payload))

        return UniversalIngestionResult(payloads=payloads, records=records, skipped_sources=skipped)

    def write_jsonl(self, records: list[NormalizedRecord], country_iso3: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / f"{country_iso3.lower()}_normalized_records.jsonl"
        with output_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(asdict(record), ensure_ascii=False, default=str) + "\n")
        return output_path


class BaseRegistryIngestor:
    def __init__(self, target_country_iso3: str | None = None) -> None:
        self.target_country_iso3 = target_country_iso3

    def fetch(self, source: SourceDefinition) -> SourcePayload:
        if source.is_local_file:
            path = source.resolved_path(BASE_DIR)
            if not path or not path.exists():
                raise FileNotFoundError(f"Missing source file for {source.id}: {path}")
            raw_text = None
            if source.source_type in {"csv", "pdf", "html", "json"}:
                raw_text = path.read_text(encoding="utf-8", errors="ignore") if source.source_type != "pdf" else None
            return SourcePayload(
                source_name=source.name,
                source_uri=str(path),
                local_path=path,
                content_type=_content_type(source.source_type),
                raw_text=raw_text,
                metadata=_payload_metadata(source),
            )

        if source.is_api:
            if not source.endpoint:
                raise ValueError(f"API source {source.id} has no endpoint")
            params = {"api-key": os.getenv(source.api_key_env or ""), "format": "json", "limit": "1000"}
            response = requests.get(source.endpoint, params=params, timeout=30)
            response.raise_for_status()
            return SourcePayload(
                source_name=source.name,
                source_uri=source.endpoint,
                content_type="application/json",
                raw_text=response.text,
                metadata=_payload_metadata(source),
            )

        raise ValueError(f"Unsupported source type for {source.id}: {source.source_type}")

    def _base_record(
        self,
        source: SourceDefinition,
        record_type: str,
        period: str,
        region: str | None,
        value: float | int | str | None,
        unit: str | None,
        metadata: dict[str, Any],
        region_code: str | None = None,
        admin_level: int | None = None,
        observed_at: str | None = None,
    ) -> NormalizedRecord:
        return NormalizedRecord(
            source_name=source.name,
            source_id=source.id,
            record_type=record_type,
            period=period,
            region=region,
            value=value,
            unit=unit,
            metadata=metadata,
            country_iso3=source.country_iso3 if source.country_iso3 != "GLOBAL" else self.target_country_iso3,
            region_code=region_code,
            admin_level=admin_level,
            observed_at=observed_at,
            provenance=source.provenance,
        )


class IndiaEnergyIngestor(BaseRegistryIngestor):
    def normalize(self, payload: SourcePayload) -> list[NormalizedRecord]:
        source = _source_from_payload(payload)
        frame = pd.read_csv(_require_path(payload))
        records: list[NormalizedRecord] = []
        for row_number, row in frame.iterrows():
            category = _clean(row.get("Category"))
            variable = _clean(row.get("Variable"))
            subcategory = _clean(row.get("Subcategory"))
            record_type = _slug("_".join(part for part in [category, subcategory, variable] if part))
            records.append(
                self._base_record(
                    source=source,
                    record_type=record_type,
                    period=str(row.get("Year", "unknown")),
                    region=_clean(row.get("State")),
                    region_code=_clean(row.get("State code")),
                    admin_level=1,
                    value=_coerce_number(row.get("Value")),
                    unit=_clean(row.get("Unit")),
                    metadata={
                        "row_number": int(row_number) + 2,
                        "country": _clean(row.get("Country")),
                        "country_code": _clean(row.get("Country code")),
                        "state_type": _clean(row.get("State type")),
                        "category": category,
                        "subcategory": subcategory,
                        "variable": variable,
                        "yoy_absolute_change": _coerce_number(row.get("YoY absolute change")),
                        "yoy_percent_change": _coerce_number(row.get("YoY % change")),
                    },
                )
            )
        return records


class GlobalCoalPlantTrackerIngestor(BaseRegistryIngestor):
    def normalize(self, payload: SourcePayload) -> list[NormalizedRecord]:
        source = _source_from_payload(payload)
        sheet = source.metadata.get("sheet", "Units")
        frame = pd.read_excel(_require_path(payload), sheet_name=sheet)
        if self.target_country_iso3:
            iso_col = "Country ISO 3"
            if iso_col in frame.columns:
                frame = frame[frame[iso_col].astype(str).str.upper() == self.target_country_iso3.upper()]

        records: list[NormalizedRecord] = []
        for row_number, row in frame.iterrows():
            plant = _clean(row.get("Plant name"))
            unit = _clean(row.get("Unit name"))
            status = _clean(row.get("Status"))
            state = _clean(row.get("Subnational unit (province, state)"))
            country_iso3 = _clean(row.get("Country ISO 3")) or self.target_country_iso3
            metadata = {column: _json_value(row.get(column)) for column in frame.columns}
            metadata["row_number"] = int(row_number) + 2
            metadata["plant_name"] = plant
            metadata["unit_name"] = unit
            metadata["status"] = status
            records.append(
                NormalizedRecord(
                    source_name=source.name,
                    source_id=source.id,
                    record_type="coal_unit_capacity",
                    period=str(row.get("Start year") or "unknown"),
                    region=state,
                    value=_coerce_number(row.get("Capacity (MW)")),
                    unit="MW",
                    metadata=metadata,
                    country_iso3=country_iso3,
                    region_code=None,
                    admin_level=1 if state else None,
                    observed_at=None,
                    provenance=source.provenance,
                )
            )
        return records


class GenericPdfStudyIngestor(BaseRegistryIngestor):
    def normalize(self, payload: SourcePayload) -> list[NormalizedRecord]:
        source = _source_from_payload(payload)
        path = _require_path(payload)
        pages = _extract_pdf_pages(path)
        records: list[NormalizedRecord] = []
        for page_number, text in enumerate(pages, start=1):
            if not text.strip():
                continue
            records.append(
                self._base_record(
                    source=source,
                    record_type="document_page",
                    period=source.provenance.get("release", "unknown"),
                    region=None,
                    value=None,
                    unit=None,
                    metadata={
                        "page_number": page_number,
                        "text": " ".join(text.split()),
                        "regions": source.metadata.get("regions", []),
                        "pollutants": source.metadata.get("pollutants", []),
                        "evidence_type": source.metadata.get("evidence_type", "document"),
                    },
                )
            )
        return records


class IndiaAQIIngestor(BaseRegistryIngestor):
    def normalize(self, payload: SourcePayload) -> list[NormalizedRecord]:
        source = _source_from_payload(payload)
        if not payload.raw_text:
            return []
        document = json.loads(payload.raw_text)
        rows = document.get("records", []) if isinstance(document, dict) else []
        records: list[NormalizedRecord] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            state = _clean(row.get("state"))
            city = _clean(row.get("city"))
            station = _clean(row.get("station"))
            pollutant = _clean(row.get("pollutant_id") or row.get("pollutant"))
            records.append(
                self._base_record(
                    source=source,
                    record_type="air_quality_observation",
                    period=_clean(row.get("last_update")) or "unknown",
                    region=state,
                    value=_coerce_number(row.get("pollutant_avg") or row.get("avg_value") or row.get("pollutant_value")),
                    unit="AQI" if pollutant == "AQI" else None,
                    metadata={
                        "record_number": index + 1,
                        "state": state,
                        "city": city,
                        "station": station,
                        "pollutant": pollutant,
                        "min": _coerce_number(row.get("pollutant_min")),
                        "max": _coerce_number(row.get("pollutant_max")),
                        "raw": row,
                    },
                    observed_at=_clean(row.get("last_update")),
                )
            )
        return records


def build_ingestor(source: SourceDefinition, target_country_iso3: str | None = None) -> UniversalIngestor:
    adapters: dict[str, type[BaseRegistryIngestor]] = {
        "IndiaEnergyIngestor": IndiaEnergyIngestor,
        "GlobalCoalPlantTrackerIngestor": GlobalCoalPlantTrackerIngestor,
        "GenericPdfStudyIngestor": GenericPdfStudyIngestor,
        "IndiaAQIIngestor": IndiaAQIIngestor,
    }
    try:
        return adapters[source.adapter](target_country_iso3=target_country_iso3)
    except KeyError as exc:
        raise ValueError(f"No ingestor registered for adapter: {source.adapter}") from exc


def _payload_metadata(source: SourceDefinition) -> dict[str, Any]:
    return {
        "source_definition": {
            "id": source.id,
            "name": source.name,
            "source_type": source.source_type,
            "adapter": source.adapter,
            "country_iso3": source.country_iso3,
            "path": source.path,
            "endpoint": source.endpoint,
            "update_frequency": source.update_frequency,
            "provenance": source.provenance,
            "metadata": source.metadata,
        }
    }


def _source_from_payload(payload: SourcePayload) -> SourceDefinition:
    source = (payload.metadata or {}).get("source_definition")
    if not source:
        raise ValueError(f"Payload missing source definition: {payload.source_name}")
    return SourceDefinition(
        id=source["id"],
        name=source["name"],
        source_type=source["source_type"],
        adapter=source["adapter"],
        country_iso3=source.get("country_iso3"),
        path=source.get("path"),
        endpoint=source.get("endpoint"),
        update_frequency=source.get("update_frequency", "unknown"),
        provenance=source.get("provenance", {}),
        metadata=source.get("metadata", {}),
    )


def _content_type(source_type: str) -> str:
    return {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
        "json": "application/json",
        "html": "text/html",
    }.get(source_type, "application/octet-stream")


def _require_path(payload: SourcePayload) -> Path:
    if not payload.local_path:
        raise ValueError(f"Payload has no local path: {payload.source_name}")
    return payload.local_path


def _extract_pdf_pages(path: Path) -> list[str]:
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return [page.extract_text() or "" for page in pdf.pages]
    except Exception:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(path))
        return [page.extract_text() or "" for page in reader.pages]


def _coerce_number(value: Any) -> float | int | str | None:
    if pd.isna(value):
        return None
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        return str(value) if value is not None else None


def _clean(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "_" for char in value]
    return "_".join("".join(chars).split("_")).strip("_")


def _json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value
