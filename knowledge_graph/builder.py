from __future__ import annotations

from pathlib import Path

import networkx as nx

from ingestion.base import NormalizedRecord

from .node_types import EdgeRecord, NodeRecord


class KnowledgeGraphBuilder:
    def __init__(self) -> None:
        self.graph = nx.DiGraph()

    def add_node(self, node: NodeRecord) -> None:
        self.graph.add_node(node.id, kind=node.kind, label=node.label, **(node.properties or {}))

    def add_edge(self, edge: EdgeRecord) -> None:
        self.graph.add_edge(edge.source, edge.target, kind=edge.kind, **(edge.properties or {}))

    def add_record(self, record: NormalizedRecord) -> str:
        node_id = self._record_node_id(record)
        self.add_node(
            NodeRecord(
                id=node_id,
                kind="Record",
                label=f"{record.source_name}:{record.record_type}",
                properties={
                    "source_name": record.source_name,
                    "record_type": record.record_type,
                    "period": record.period,
                    "region": record.region,
                    "value": record.value,
                    "unit": record.unit,
                    **(record.metadata or {}),
                },
            )
        )
        if record.region:
            region_node = f"region::{record.region}"
            self.add_node(NodeRecord(id=region_node, kind="Region", label=record.region, properties={"region": record.region}))
            self.add_edge(EdgeRecord(source=node_id, target=region_node, kind="DERIVED_FROM", properties={"relation": "region"}))
        return node_id

    def build_from_records(self, records: list[NormalizedRecord]) -> nx.DiGraph:
        for record in records:
            self.add_record(record)
        return self.graph

    def save(self, path: str | Path) -> None:
        nx.write_gexf(self.graph, Path(path))

    def _record_node_id(self, record: NormalizedRecord) -> str:
        region = record.region or "global"
        return f"record::{record.source_name}::{record.record_type}::{record.period}::{region}"
