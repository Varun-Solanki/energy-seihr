from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.source_registry import load_source_registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate configured EPIGRID data sources.")
    parser.add_argument("--country", help="ISO3 country code, e.g. IND")
    args = parser.parse_args()

    registry = load_source_registry()
    country = args.country.upper() if args.country else None
    checks = registry.validate(country_iso3=country)

    print(f"Source registry v{registry.version}")
    if country:
        print(f"Country: {country}")
    else:
        countries = ", ".join(item.iso3 for item in registry.list_countries())
        print(f"Countries: {countries or 'none'}")

    ok_count = sum(item.ok for item in checks)
    print(f"Sources: {ok_count}/{len(checks)} available")
    for item in checks:
        label = "OK" if item.ok else item.status.upper()
        country_label = item.country_iso3 or "GLOBAL"
        print(f"[{label}] {country_label} {item.source_id} ({item.source_type}) - {item.message}")

    if any(not item.ok for item in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
