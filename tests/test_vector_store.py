from rag.evidence_store import EvidenceChunk
from rag.vector_store import ChromaEvidenceStore, HashingEmbeddingModel


def test_hashing_embedding_is_deterministic() -> None:
    model = HashingEmbeddingModel(dimension=32)

    assert model.embed("coal capacity in India") == model.embed("coal capacity in India")
    assert len(model.embed("coal capacity in India")) == 32


def test_chroma_indexes_and_queries_chunks(tmp_path) -> None:
    store = ChromaEvidenceStore(
        persist_dir=tmp_path / "chroma",
        collection_name="test_evidence",
        embedding_model=HashingEmbeddingModel(dimension=64),
    )
    store.reset_collection()
    chunks = [
        EvidenceChunk(
            chunk_id="chunk::coal",
            source_id="global_coal_plant_tracker_2026_07",
            source_name="Coal tracker",
            chunk_type="structured_fact",
            content="Mundra Thermal Power Station is an operating coal unit in Gujarat, India.",
            country_iso3="IND",
            region="Gujarat",
            period="2024",
            metadata={"fuel": "Coal"},
        ),
        EvidenceChunk(
            chunk_id="chunk::solar",
            source_id="ind_energy_yearly_state",
            source_name="India energy",
            chunk_type="structured_fact",
            content="In 2024, Rajasthan reported solar electricity generation.",
            country_iso3="IND",
            region="Rajasthan",
            period="2024",
            metadata={"fuel": "Solar"},
        ),
    ]

    assert store.index_chunks(chunks, batch_size=1) == 2
    assert store.count() == 2

    results = store.query("coal plant in Gujarat", n_results=1, where={"country_iso3": "IND"})

    assert len(results) == 1
    assert results[0].chunk_id == "chunk::coal"
    assert results[0].metadata["region"] == "Gujarat"


def test_chroma_hybrid_query_reranks_exact_scientific_terms(tmp_path) -> None:
    store = ChromaEvidenceStore(
        persist_dir=tmp_path / "chroma",
        collection_name="test_hybrid_evidence",
        embedding_model=HashingEmbeddingModel(dimension=64),
    )
    store.reset_collection()
    store.index_chunks(
        [
            EvidenceChunk(
                chunk_id="chunk::table",
                source_id="ind_energy_yearly_state",
                source_name="India energy",
                chunk_type="structured_fact",
                content="In 2024, Punjab reported clean power sector emissions.",
                country_iso3="IND",
                region="Punjab",
            ),
            EvidenceChunk(
                chunk_id="chunk::study",
                source_id="ind_delhi_ncr_pm25_crb_study_2025",
                source_name="Delhi NCR PM2.5 study",
                chunk_type="document_chunk",
                content="Delhi-NCR PM2.5 showed weak coupling with crop residue burning in Punjab and Haryana.",
                country_iso3="IND",
            ),
        ]
    )

    results = store.query("Delhi PM2.5 crop residue burning Punjab", n_results=1, where={"country_iso3": "IND"}, hybrid=True)

    assert results[0].chunk_id == "chunk::study"
