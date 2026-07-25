from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests

from .base import NormalizedRecord, SourcePayload


class FingertipsClient:
    source_name = "nhs_fingertips"

    def fetch(self, source_uri: str, local_path: Path | None = None) -> SourcePayload:
        raw_text = self._read_or_download(source_uri, local_path)
        return SourcePayload(
            source_name=self.source_name,
            source_uri=source_uri,
            local_path=local_path,
            content_type="text/html",
            raw_text=raw_text,
            metadata={"source_family": "fingertips"},
        )

    def normalize(self, payload: SourcePayload) -> list[NormalizedRecord]:
        if not payload.raw_text:
            return []
        text = self._strip_html(payload.raw_text)
        return [
            NormalizedRecord(
                source_name=self.source_name,
                record_type="health_indicator",
                period="unknown",
                region=None,
                value=None,
                unit=None,
                metadata={"preview": text[:500]},
            )
        ]

    def _read_or_download(self, source_uri: str, local_path: Path | None) -> str:
        if local_path is not None and local_path.exists():
            return local_path.read_text(encoding="utf-8")
        response = requests.get(source_uri, timeout=30)
        response.raise_for_status()
        if local_path is not None:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(response.text, encoding="utf-8")
        return response.text

    def _strip_html(self, html: str) -> str:
        parser = _TextOnlyParser()
        parser.feed(html)
        return " ".join(parser.parts)


class _TextOnlyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        clean = data.strip()
        if clean:
            self.parts.append(clean)
