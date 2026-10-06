from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.source_registry import load_source_registry
from ingestion.phase2 import RegistryIngestionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest registered EPIGRID sources into normalized JSONL records.")
    parser.add_argument("--country", default="IND", help="ISO3 country code to ingest, e.g. IND")
    parser.add_argument("--include-live-apis", action="store_true", help="Fetch live API sources such as real-time AQI")
    args = parser.parse_args()

    country = args.country.upper()
    pipeline = RegistryIngestionPipeline(load_source_registry(), include_live_apis=args.include_live_apis)
    result = pipeline.run_country(country)
    output_path = pipeline.write_jsonl(result.records, country)

    print(f"Ingested country: {country}")
    print(f"Payloads fetched: {len(result.payloads)}")
    print(f"Records written: {len(result.records)}")
    print(f"Output: {output_path}")
    if result.skipped_sources:
        print("Skipped sources:")
        for item in result.skipped_sources:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
