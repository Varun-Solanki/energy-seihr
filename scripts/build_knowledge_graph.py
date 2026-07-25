from __future__ import annotations

import json
from pathlib import Path
import sys

from ingestion.base import NormalizedRecord
from knowledge_graph.builder import KnowledgeGraphBuilder


def load_records(path: str | Path) -> list[NormalizedRecord]:
    file_path = Path(path)
    records: list[NormalizedRecord] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        records.append(NormalizedRecord(**payload))
    return records


def build_graph(records_path: str | Path, output_path: str | Path) -> None:
    builder = KnowledgeGraphBuilder()
    records = load_records(records_path)
    builder.build_from_records(records)
    builder.save(output_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/build_knowledge_graph.py <records_jsonl> <graph_gexf>")
        raise SystemExit(1)
    build_graph(sys.argv[1], sys.argv[2])
