from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .settings import BASE_DIR, settings


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    name: str
    source_type: str
    adapter: str
    country_iso3: str | None = None
    path: str | None = None
    endpoint: str | None = None
    api_key_env: str | None = None
    update_frequency: str = "unknown"
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_local_file(self) -> bool:
        return self.source_type in {"csv", "xlsx", "pdf", "json", "html"} and bool(self.path)

    @property
    def is_api(self) -> bool:
        return self.source_type == "api" and bool(self.endpoint)

    def resolved_path(self, base_dir: Path = BASE_DIR) -> Path | None:
        if not self.path:
            return None
        path = Path(self.path)
        return path if path.is_absolute() else base_dir / path


@dataclass(frozen=True)
class CountryDefinition:
    iso3: str
    name: str
    iso2: str | None = None
    default_admin_level: int | None = None
    sources: tuple[SourceDefinition, ...] = ()


@dataclass(frozen=True)
class SourceAvailability:
    source_id: str
    source_type: str
    country_iso3: str | None
    status: str
    message: str

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class SourceRegistry:
    def __init__(
        self,
        countries: list[CountryDefinition],
        shared_sources: list[SourceDefinition],
        version: int,
        description: str = "",
    ) -> None:
        self.countries = {country.iso3: country for country in countries}
        self.shared_sources = tuple(shared_sources)
        self.version = version
        self.description = description

    @classmethod
    def from_file(cls, path: str | Path | None = None) -> "SourceRegistry":
        registry_path = Path(path or settings.source_registry_path)
        with registry_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        countries = [
            CountryDefinition(
                iso3=country["iso3"],
                iso2=country.get("iso2"),
                name=country["name"],
                default_admin_level=country.get("default_admin_level"),
                sources=tuple(
                    _source_from_dict(source, default_country_iso3=country["iso3"])
                    for source in country.get("sources", [])
                ),
            )
            for country in payload.get("countries", [])
        ]
        shared_sources = [
            _source_from_dict(source, default_country_iso3=source.get("metadata", {}).get("country_iso3"))
            for source in payload.get("shared_sources", [])
        ]
        return cls(
            countries=countries,
            shared_sources=shared_sources,
            version=payload.get("version", 1),
            description=payload.get("description", ""),
        )

    def list_countries(self) -> list[CountryDefinition]:
        return sorted(self.countries.values(), key=lambda country: country.iso3)

    def sources_for_country(self, country_iso3: str, include_shared: bool = True) -> list[SourceDefinition]:
        country = self.countries.get(country_iso3.upper())
        country_sources = list(country.sources) if country else []
        if include_shared:
            return [*country_sources, *self.shared_sources]
        return country_sources

    def all_sources(self) -> list[SourceDefinition]:
        sources: list[SourceDefinition] = []
        for country in self.list_countries():
            sources.extend(country.sources)
        sources.extend(self.shared_sources)
        return sources

    def validate(self, country_iso3: str | None = None, base_dir: Path = BASE_DIR) -> list[SourceAvailability]:
        sources = self.sources_for_country(country_iso3, include_shared=True) if country_iso3 else self.all_sources()
        return [_validate_source(source, base_dir) for source in sources]


def _source_from_dict(payload: dict[str, Any], default_country_iso3: str | None) -> SourceDefinition:
    metadata = payload.get("metadata", {})
    return SourceDefinition(
        id=payload["id"],
        name=payload["name"],
        source_type=payload["source_type"],
        adapter=payload["adapter"],
        country_iso3=metadata.get("country_iso3", default_country_iso3),
        path=payload.get("path"),
        endpoint=payload.get("endpoint"),
        api_key_env=payload.get("api_key_env"),
        update_frequency=payload.get("update_frequency", "unknown"),
        provenance=payload.get("provenance", {}),
        metadata=metadata,
    )


def _validate_source(source: SourceDefinition, base_dir: Path) -> SourceAvailability:
    if source.is_local_file:
        path = source.resolved_path(base_dir)
        if path and path.exists():
            return SourceAvailability(source.id, source.source_type, source.country_iso3, "ok", str(path))
        return SourceAvailability(source.id, source.source_type, source.country_iso3, "missing", f"Missing local file: {path}")

    if source.is_api:
        if not source.endpoint:
            return SourceAvailability(source.id, source.source_type, source.country_iso3, "missing", "Missing API endpoint")
        if source.api_key_env and not os.getenv(source.api_key_env):
            return SourceAvailability(
                source.id,
                source.source_type,
                source.country_iso3,
                "missing",
                f"Missing environment variable: {source.api_key_env}",
            )
        return SourceAvailability(source.id, source.source_type, source.country_iso3, "ok", source.endpoint)

    return SourceAvailability(source.id, source.source_type, source.country_iso3, "warning", "No validator for this source type")


def load_source_registry() -> SourceRegistry:
    return SourceRegistry.from_file()
