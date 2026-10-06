from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    source_id: str
    source_name: str
    chunk_type: str
    content: str
    country_iso3: str | None = None
    region: str | None = None
    region_code: str | None = None
    period: str | None = None
    unit: str | None = None
    value: float | int | str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceBuildResult:
    output_path: Path
    manifest_path: Path
    chunk_count: int
    counts_by_type: dict[str, int]
    counts_by_source: dict[str, int]


class EvidenceStoreBuilder:
    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        manifest_path: Path | None = None,
        document_chunk_words: int = 700,
        document_overlap_words: int = 90,
    ) -> None:
        self.input_path = input_path
        self.output_path = output_path
        self.manifest_path = manifest_path or output_path.with_suffix(".manifest.json")
        self.document_chunk_words = document_chunk_words
        self.document_overlap_words = document_overlap_words

    def build(self) -> EvidenceBuildResult:
        chunks = list(build_evidence_chunks(read_normalized_records(self.input_path), self.document_chunk_words, self.document_overlap_words))
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("w", encoding="utf-8") as handle:
            for chunk in chunks:
                handle.write(json.dumps(chunk.to_json(), ensure_ascii=False, default=str) + "\n")

        counts_by_type = _count_by(chunks, "chunk_type")
        counts_by_source = _count_by(chunks, "source_id")
        manifest = {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "chunk_count": len(chunks),
            "counts_by_type": counts_by_type,
            "counts_by_source": counts_by_source,
            "document_chunk_words": self.document_chunk_words,
            "document_overlap_words": self.document_overlap_words,
        }
        with self.manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)

        return EvidenceBuildResult(
            output_path=self.output_path,
            manifest_path=self.manifest_path,
            chunk_count=len(chunks),
            counts_by_type=counts_by_type,
            counts_by_source=counts_by_source,
        )


def read_normalized_records(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def build_evidence_chunks(
    records: Iterable[dict[str, Any]],
    document_chunk_words: int = 700,
    document_overlap_words: int = 90,
) -> Iterable[EvidenceChunk]:
    for record in records:
        if record.get("record_type") == "document_page":
            yield from _document_chunks(record, document_chunk_words, document_overlap_words)
        else:
            chunk = _structured_fact_chunk(record)
            if chunk.content.strip():
                yield chunk


def _document_chunks(record: dict[str, Any], chunk_words: int, overlap_words: int) -> Iterable[EvidenceChunk]:
    metadata = record.get("metadata") or {}
    text = " ".join(str(metadata.get("text") or "").split())
    if not text:
        return

    source_id = record.get("source_id") or record.get("source_name") or "unknown_source"
    page_number = metadata.get("page_number")
    for chunk_index, chunk_text in enumerate(_split_words(text, chunk_words, overlap_words), start=1):
        chunk_metadata = _base_metadata(record)
        chunk_metadata.update(
            {
                "page_number": page_number,
                "chunk_index": chunk_index,
                "regions": metadata.get("regions", []),
                "pollutants": metadata.get("pollutants", []),
                "evidence_type": metadata.get("evidence_type", "document"),
            }
        )
        yield EvidenceChunk(
            chunk_id=_chunk_id(source_id, "document_chunk", record.get("period"), page_number, chunk_index, chunk_text),
            source_id=source_id,
            source_name=record.get("source_name") or source_id,
            chunk_type="document_chunk",
            content=chunk_text,
            country_iso3=record.get("country_iso3"),
            region=record.get("region"),
            region_code=record.get("region_code"),
            period=record.get("period"),
            metadata=chunk_metadata,
            provenance=record.get("provenance") or {},
        )


def _structured_fact_chunk(record: dict[str, Any]) -> EvidenceChunk:
    source_id = record.get("source_id") or record.get("source_name") or "unknown_source"
    metadata = record.get("metadata") or {}
    content = _fact_sentence(record)
    row_number = metadata.get("row_number") or metadata.get("record_number")
    return EvidenceChunk(
        chunk_id=_chunk_id(source_id, record.get("record_type"), record.get("period"), record.get("region"), row_number, content),
        source_id=source_id,
        source_name=record.get("source_name") or source_id,
        chunk_type="structured_fact",
        content=content,
        country_iso3=record.get("country_iso3"),
        region=record.get("region"),
        region_code=record.get("region_code"),
        period=record.get("period"),
        unit=record.get("unit"),
        value=record.get("value"),
        metadata=_base_metadata(record),
        provenance=record.get("provenance") or {},
    )


def _fact_sentence(record: dict[str, Any]) -> str:
    metadata = record.get("metadata") or {}
    source_id = record.get("source_id") or ""
    region = record.get("region") or "unknown region"
    period = record.get("period") or "unknown period"
    value = record.get("value")
    unit = record.get("unit") or ""

    if source_id == "ind_energy_yearly_state":
        category = metadata.get("category") or "metric"
        variable = metadata.get("variable") or record.get("record_type")
        subcategory = metadata.get("subcategory")
        descriptor = f"{category}"
        if subcategory:
            descriptor += f" / {subcategory}"
        return f"In {period}, {region}, {record.get('country_iso3')}, reported {descriptor} for {variable}: {_value_text(value, unit)}."

    if source_id == "global_coal_plant_tracker_2026_07":
        plant = metadata.get("plant_name") or metadata.get("Plant name") or "unknown plant"
        unit_name = metadata.get("unit_name") or metadata.get("Unit name") or "unknown unit"
        status = metadata.get("status") or metadata.get("Status") or "unknown status"
        fuel = metadata.get("Coal type") or "coal"
        owner = metadata.get("Owner")
        location = ", ".join(part for part in [metadata.get("Location"), region, metadata.get("Country/Area")] if part)
        owner_text = f" Owner: {owner}." if owner else ""
        return (
            f"{plant} {unit_name} is a {status} {fuel} coal unit in {location}. "
            f"Capacity is {_value_text(value, unit)}; start year is {period}.{owner_text}"
        )

    if record.get("record_type") == "air_quality_observation":
        city = metadata.get("city")
        station = metadata.get("station")
        pollutant = metadata.get("pollutant") or "air quality"
        place = ", ".join(part for part in [station, city, region, record.get("country_iso3")] if part)
        return f"At {period}, {place} reported {pollutant}: {_value_text(value, unit)}."

    return f"In {period}, {region}, {record.get('country_iso3')}, {record.get('record_type')} was {_value_text(value, unit)}."


def _base_metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(record.get("metadata") or {})
    metadata.pop("text", None)
    metadata.pop("raw", None)
    metadata.update(
        {
            "source_id": record.get("source_id"),
            "record_type": record.get("record_type"),
            "country_iso3": record.get("country_iso3"),
            "admin_level": record.get("admin_level"),
            "observed_at": record.get("observed_at"),
        }
    )
    return metadata


def _split_words(text: str, chunk_words: int, overlap_words: int) -> Iterable[str]:
    words = text.split()
    if not words:
        return
    step = max(1, chunk_words - overlap_words)
    for start in range(0, len(words), step):
        chunk = words[start : start + chunk_words]
        if not chunk:
            break
        yield " ".join(chunk)
        if start + chunk_words >= len(words):
            break


def _chunk_id(*parts: Any) -> str:
    raw = "|".join(str(part) for part in parts if part is not None)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"chunk::{digest}"


def _value_text(value: Any, unit: str | None) -> str:
    if value is None:
        return "not available"
    if unit:
        return f"{value} {unit}"
    return str(value)


def _count_by(chunks: list[EvidenceChunk], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        value = str(getattr(chunk, field_name))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
