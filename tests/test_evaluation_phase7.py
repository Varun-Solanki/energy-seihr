import pytest
from pathlib import Path

from rag.retriever import Retriever, RetrievedContext
from rag.vector_store import ChromaEvidenceStore
from rag.evidence_store import EvidenceChunk
from knowledge_graph.querier import KnowledgeGraphQuerier
from core.runner import SimulationRunner, Scenario
from core.parameters import ModelParameters
from scripts.run_scenario import ensure_default_graph


def test_graphrag_retrieval_flow(tmp_path: Path) -> None:
    """Evaluation: Test that GraphRAG retrieves from Vector DB and Knowledge Graph."""
    store = ChromaEvidenceStore(persist_dir=tmp_path / "chroma", collection_name="test_retrieval")
    store.index_chunks([
        EvidenceChunk(
            chunk_id="chk1",
            source_id="src1",
            source_name="Test Source",
            chunk_type="fact",
            content="Delhi coal generation is extremely high in winter."
        )
    ])
    
    graph_path = tmp_path / "graph.gexf"
    ensure_default_graph(graph_path)
    
    retriever = Retriever(graph_path=graph_path, cache_dir=tmp_path / "cache")
    retriever.vector_store = store
    
    context = retriever.retrieve("Delhi coal", region="UK_Yorkshire", use_cache=False)
    
    # Assert Semantic Chunks
    assert context.vector_results is not None
    assert len(context.vector_results) > 0
    assert "Delhi" in context.vector_results[0]["content"]
    
    # Assert Graph Paths
    assert len(context.graph_context) > 0


def test_graph_integrity(tmp_path: Path) -> None:
    """Evaluation: Test that Knowledge Graph maintains schema constraints."""
    graph_path = tmp_path / "graph.gexf"
    ensure_default_graph(graph_path)
    querier = KnowledgeGraphQuerier(graph_path)
    
    for node, data in querier.graph.nodes(data=True):
        assert "kind" in data
        assert "label" in data
        
        if data["kind"] == "Region":
            records = querier.records_for_region(data["region"])
            assert isinstance(records, list)


def test_answer_citation_formatting() -> None:
    """Evaluation: Test that retrieved evidence retains strict citation mapping for LLM."""
    context = RetrievedContext(
        query="Test query",
        tavily_results=[],
        graph_context=["event::test_closure_2023"],
        local_documents=[{"path": "doc.html", "title": "Doc", "snippet": "Snippet"}],
        vector_results=[{"chunk_id": "c1", "score": 0.9, "content": "Text", "metadata": {"source_name": "Report Citation"}}],
        timestamp="2023-01-01",
        cache_hit=False
    )
    retriever = Retriever()
    formatted = retriever.format_for_llm(context)
    
    assert "VECTOR DB SEMANTIC SEARCH RESULTS" in formatted
    assert "[Chunk c1]" in formatted
    assert "Source: Report Citation" in formatted
    assert "event::test_closure_2023" in formatted


def test_scenario_regression() -> None:
    """Evaluation: Test that identical inputs yield perfectly identical numeric scenario outputs (Deterministic Regression)."""
    runner = SimulationRunner()
    params = ModelParameters(
        region="Regression_Test",
        beta_base=0.5, sigma=0.2, gamma=0.1, eta=0.05, rho=0.1, omega=0.01,
        beta_sensitivity=1.0, x_scale=0.5, kappa=0.02, lambda_rate=0.08,
        psi_transport=0.001, phi_transport=0.002, transboundary_lag_days=30,
        s0=1000, e0=10, i0=5, h0=1, r0=0, x0=0.5,
        pollution_lag_days=90, policy_response_days=180
    )
    
    scenario = Scenario(
        description="Regression run",
        start_date="2023-01-01",
        end_date="2023-01-10",
        regions=["Regression_Test"],
        parameters={"Regression_Test": params},
        coupling_matrix={}
    )
    
    output1 = runner.run(scenario)
    output2 = runner.run(scenario)
    
    assert len(output1.trajectory["Regression_Test"].time) == 10
    assert (output1.trajectory["Regression_Test"].trajectory == output2.trajectory["Regression_Test"].trajectory).all()
