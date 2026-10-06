from config.source_registry import load_source_registry
from ingestion.phase2 import (
    GenericPdfStudyIngestor,
    GlobalCoalPlantTrackerIngestor,
    IndiaEnergyIngestor,
    RegistryIngestionPipeline,
)


def test_india_energy_ingestor_normalizes_state_year_metrics() -> None:
    registry = load_source_registry()
    source = next(item for item in registry.sources_for_country("IND") if item.id == "ind_energy_yearly_state")
    ingestor = IndiaEnergyIngestor(target_country_iso3="IND")

    records = ingestor.normalize(ingestor.fetch(source))

    assert records
    first = records[0]
    assert first.source_id == "ind_energy_yearly_state"
    assert first.country_iso3 == "IND"
    assert first.region == "Andaman and Nicobar"
    assert first.period == "2019"
    assert first.unit == "MW"


def test_global_coal_tracker_filters_to_target_country() -> None:
    registry = load_source_registry()
    source = next(item for item in registry.sources_for_country("IND") if item.id == "global_coal_plant_tracker_2026_07")
    ingestor = GlobalCoalPlantTrackerIngestor(target_country_iso3="IND")

    records = ingestor.normalize(ingestor.fetch(source))

    assert records
    assert {record.country_iso3 for record in records} == {"IND"}
    assert all(record.record_type == "coal_unit_capacity" for record in records)


def test_pdf_ingestor_extracts_page_records() -> None:
    registry = load_source_registry()
    source = next(item for item in registry.sources_for_country("IND") if item.id == "ind_delhi_ncr_pm25_crb_study_2025")
    ingestor = GenericPdfStudyIngestor(target_country_iso3="IND")

    records = ingestor.normalize(ingestor.fetch(source))

    assert len(records) >= 5
    assert records[0].record_type == "document_page"
    assert "PM" in records[0].metadata["text"]


def test_registry_pipeline_writes_normalized_records(tmp_path) -> None:
    pipeline = RegistryIngestionPipeline(load_source_registry(), output_dir=tmp_path)

    result = pipeline.run_country("IND")
    output = pipeline.write_jsonl(result.records, "IND")

    assert output.exists()
    assert result.records
    assert any(item.startswith("ind_realtime_aqi") for item in result.skipped_sources)
