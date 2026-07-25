from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from config import settings
from ingestion.pipeline import IngestionPipeline


OUTPUT_FILE = Path("data/processed/normalized_records.jsonl")


def main() -> None:
    if not settings.data_carbon_intensity_api or not settings.data_defra_pm25 or not settings.data_nhs_fingertips:
        raise SystemExit("Missing one or more required source URLs in the environment")

    pipeline = IngestionPipeline()
    result = pipeline.run(
        national_grid_uri=settings.data_carbon_intensity_api,
        defra_uri=settings.data_defra_pm25,
        fingertips_uri=settings.data_nhs_fingertips,
        local_root=Path("data/raw"),
    )
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as handle:
        for record in result.records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    print(f"Wrote {len(result.records)} normalized records to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
