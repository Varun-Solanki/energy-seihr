import json

from rag.evidence_store import EvidenceStoreBuilder, build_evidence_chunks


def test_builds_structured_fact_chunk_from_energy_record() -> None:
    record = {
        "source_id": "ind_energy_yearly_state",
        "source_name": "India yearly state energy",
        "record_type": "capacity_fuel_coal",
        "period": "2024",
        "region": "India Total",
        "region_code": "IND",
        "country_iso3": "IND",
        "value": 219059.84,
        "unit": "MW",
        "metadata": {"category": "Capacity", "subcategory": "Fuel", "variable": "Coal", "row_number": 10},
        "provenance": {"publisher": "test"},
    }

    chunks = list(build_evidence_chunks([record]))

    assert len(chunks) == 1
    assert chunks[0].chunk_type == "structured_fact"
    assert "Coal" in chunks[0].content
    assert "219059.84 MW" in chunks[0].content
    assert chunks[0].country_iso3 == "IND"


def test_splits_document_pages_with_provenance() -> None:
    record = {
        "source_id": "study",
        "source_name": "Study",
        "record_type": "document_page",
        "period": "2025",
        "region": None,
        "country_iso3": "IND",
        "metadata": {
            "page_number": 3,
            "text": " ".join(f"word{i}" for i in range(25)),
            "regions": ["Delhi"],
            "pollutants": ["PM2.5"],
        },
        "provenance": {"doi": "example"},
    }

    chunks = list(build_evidence_chunks([record], document_chunk_words=10, document_overlap_words=2))

    assert len(chunks) == 3
    assert chunks[0].metadata["page_number"] == 3
    assert chunks[0].metadata["regions"] == ["Delhi"]
    assert chunks[0].provenance["doi"] == "example"


def test_evidence_store_builder_writes_jsonl_and_manifest(tmp_path) -> None:
    input_path = tmp_path / "records.jsonl"
    output_path = tmp_path / "chunks.jsonl"
    record = {
        "source_id": "ind_energy_yearly_state",
        "source_name": "India yearly state energy",
        "record_type": "electricity_generation_fuel_solar",
        "period": "2024",
        "region": "Gujarat",
        "country_iso3": "IND",
        "value": 100,
        "unit": "GWh",
        "metadata": {"category": "Electricity generation", "subcategory": "Fuel", "variable": "Solar"},
        "provenance": {},
    }
    input_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = EvidenceStoreBuilder(input_path=input_path, output_path=output_path).build()

    assert result.chunk_count == 1
    assert output_path.exists()
    assert result.manifest_path.exists()
    stored = json.loads(output_path.read_text(encoding="utf-8").strip())
    assert stored["region"] == "Gujarat"
