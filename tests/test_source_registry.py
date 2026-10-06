from config.source_registry import SourceRegistry, load_source_registry


def test_source_registry_loads_india_data_pack() -> None:
    registry = load_source_registry()

    countries = {country.iso3: country for country in registry.list_countries()}
    assert "IND" in countries

    source_ids = {source.id for source in registry.sources_for_country("IND")}
    assert "ind_energy_yearly_state" in source_ids
    assert "ind_realtime_aqi" in source_ids
    assert "global_coal_plant_tracker_2026_07" in source_ids


def test_local_india_sources_are_available() -> None:
    registry = SourceRegistry.from_file()

    checks = {
        check.source_id: check
        for check in registry.validate(country_iso3="IND")
        if check.source_type != "api"
    }

    assert checks["ind_energy_yearly_state"].ok
    assert checks["ind_delhi_ncr_pm25_crb_study_2025"].ok
    assert checks["global_coal_plant_tracker_2026_07"].ok
