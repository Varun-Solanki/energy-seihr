from pathlib import Path

from knowledge_graph.querier import KnowledgeGraphQuerier
from scripts.run_scenario import ensure_default_graph


def test_default_graph_contains_region_causal_context(tmp_path: Path) -> None:
    graph_path = tmp_path / "knowledge_graph.gexf"

    ensure_default_graph(graph_path)
    querier = KnowledgeGraphQuerier(graph_path)
    records = querier.records_for_region("UK_Yorkshire")

    labels = {record["label"] for record in records}
    assert "Drax coal unit closure 2023" in labels
    assert "PM2.5 linked respiratory and cardiovascular admissions" in labels
