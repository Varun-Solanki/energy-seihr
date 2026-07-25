from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx


class KnowledgeGraphQuerier:
    def __init__(self, graph_path: str | Path) -> None:
        self.graph = nx.read_gexf(Path(graph_path))

    def neighbors(self, node_id: str) -> list[str]:
        return list(self.graph.neighbors(node_id))

    def records_for_region(self, region: str) -> list[dict[str, Any]]:
        region_node = f"region::{region}"
        if region_node not in self.graph:
            return []
        records: list[dict[str, Any]] = []
        for node_id in self.graph.predecessors(region_node):
            records.append(dict(self.graph.nodes[node_id]))
        return records

    def subgraph(self, node_id: str, depth: int = 1) -> nx.DiGraph:
        nodes = {node_id}
        frontier = {node_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for item in frontier:
                next_frontier.update(self.graph.predecessors(item))
                next_frontier.update(self.graph.successors(item))
            nodes.update(next_frontier)
            frontier = next_frontier
        return self.graph.subgraph(nodes).copy()
