from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ParameterValidator:
    def __init__(self, schema_path: str | Path = "contracts/parameter_schema.json") -> None:
        self.schema_path = Path(schema_path)
        with self.schema_path.open(encoding="utf-8") as handle:
            self.schema = json.load(handle)

    def validate(self, parameters: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        defaults = defaults or {}
        validated: dict[str, Any] = {}
        properties = self.schema.get("properties", {})

        for name, spec in properties.items():
            if name not in parameters and name not in defaults:
                continue
            value = parameters.get(name, defaults.get(name))
            if value is None:
                continue

            expected_type = spec.get("type")
            try:
                if expected_type == "integer":
                    value = int(round(float(value)))
                elif expected_type == "number":
                    value = float(value)
                elif expected_type == "string":
                    value = str(value)
            except (TypeError, ValueError):
                value = defaults.get(name)
                if value is None:
                    continue

            if isinstance(value, (int, float)):
                if "minimum" in spec:
                    value = max(value, spec["minimum"])
                if "maximum" in spec:
                    value = min(value, spec["maximum"])

            validated[name] = value

        for required in self.schema.get("required", []):
            if required not in validated and required in defaults:
                validated[required] = defaults[required]

        return validated
