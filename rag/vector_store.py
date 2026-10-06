from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from config.settings import settings
from rag.evidence_store import EvidenceChunk


@dataclass(frozen=True)
class VectorSearchResult:
    chunk_id: str
    content: str
    score: float | None
    metadata: dict[str, Any]


class HashingEmbeddingModel:
    """Small deterministic embedding model for offline Chroma indexing.

    This is intentionally dependency-free. Phase 4 needs a working vector DB
    pipeline; higher-quality OpenAI or local transformer embeddings can replace
    this class later without changing evidence chunks or Chroma metadata.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if not norm:
            return vector
        return [value / norm for value in vector]


class ChromaEvidenceStore:
    def __init__(
        self,
        persist_dir: Path | None = None,
        collection_name: str = "epigrid_evidence",
        embedding_model: HashingEmbeddingModel | None = None,
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("chromadb is required for Phase 4. Install dependencies from requirements.txt.") from exc

        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.collection_name = collection_name
        self.embedding_model = embedding_model or HashingEmbeddingModel(settings.embedding_dimension)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "EPIGRID GraphRAG evidence chunks"},
        )

    def reset_collection(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "EPIGRID GraphRAG evidence chunks"},
        )

    def index_chunks(self, chunks: Iterable[EvidenceChunk], batch_size: int = 500) -> int:
        count = 0
        batch: list[EvidenceChunk] = []
        for chunk in chunks:
            batch.append(chunk)
            if len(batch) >= batch_size:
                count += self._add_batch(batch)
                batch = []
        if batch:
            count += self._add_batch(batch)
        return count

    def query(
        self,
        text: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
        hybrid: bool = False,
    ) -> list[VectorSearchResult]:
        if hybrid:
            return self.hybrid_query(text, n_results=n_results, where=where)
        result = self.collection.query(
            query_embeddings=[self.embedding_model.embed(text)],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        output: list[VectorSearchResult] = []
        for index, chunk_id in enumerate(ids):
            distance = distances[index] if index < len(distances) else None
            score = None if distance is None else 1.0 / (1.0 + float(distance))
            output.append(
                VectorSearchResult(
                    chunk_id=chunk_id,
                    content=documents[index] if index < len(documents) else "",
                    score=score,
                    metadata=metadatas[index] if index < len(metadatas) else {},
                )
            )
        return output

    def hybrid_query(
        self,
        text: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
        vector_candidates: int = 200,
    ) -> list[VectorSearchResult]:
        vector_results = self.query(text, n_results=vector_candidates, where=where, hybrid=False)
        vector_by_id = {result.chunk_id: result for result in vector_results}

        lexical_pool = self.collection.get(where=where, include=["documents", "metadatas"])
        ids = lexical_pool.get("ids", [])
        documents = lexical_pool.get("documents", [])
        metadatas = lexical_pool.get("metadatas", [])
        query_tokens = _tokens(text)
        scored: list[VectorSearchResult] = []
        for index, chunk_id in enumerate(ids):
            document = documents[index] if index < len(documents) else ""
            metadata = metadatas[index] if index < len(metadatas) else {}
            lexical_score = _lexical_score(query_tokens, document, metadata)
            vector_score = vector_by_id.get(chunk_id).score if chunk_id in vector_by_id else None
            combined = lexical_score + (0.25 * vector_score if vector_score is not None else 0.0)
            if combined <= 0:
                continue
            scored.append(VectorSearchResult(chunk_id=chunk_id, content=document, score=combined, metadata=metadata))

        scored.sort(key=lambda item: item.score or 0.0, reverse=True)
        return scored[:n_results]

    def count(self) -> int:
        return int(self.collection.count())

    def _add_batch(self, chunks: list[EvidenceChunk]) -> int:
        documents = [chunk.content for chunk in chunks]
        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=documents,
            embeddings=self.embedding_model.embed_documents(documents),
            metadatas=[_metadata_for_chroma(chunk) for chunk in chunks],
        )
        return len(chunks)


def read_evidence_chunks(path: Path) -> Iterable[EvidenceChunk]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            yield EvidenceChunk(**payload)


def _metadata_for_chroma(chunk: EvidenceChunk) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "source_name": chunk.source_name,
        "chunk_type": chunk.chunk_type,
    }
    for key, value in {
        "country_iso3": chunk.country_iso3,
        "region": chunk.region,
        "region_code": chunk.region_code,
        "period": chunk.period,
        "unit": chunk.unit,
        "value": chunk.value,
    }.items():
        _put_metadata(metadata, key, value)
    for key, value in (chunk.metadata or {}).items():
        _put_metadata(metadata, f"meta_{key}", value)
    for key, value in (chunk.provenance or {}).items():
        _put_metadata(metadata, f"prov_{key}", value)
    return metadata


def _put_metadata(metadata: dict[str, str | int | float | bool], key: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        metadata[key] = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        metadata[key] = value
    elif isinstance(value, list):
        metadata[key] = ", ".join(str(item) for item in value)
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, default=str)
        metadata[key] = text[:500]
    else:
        metadata[key] = str(value)[:500]


def _tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", text.lower())
    expanded: list[str] = []
    for token in raw_tokens:
        expanded.append(token)
        if "." in token:
            expanded.extend(part for part in token.split(".") if part)
    return expanded


def _lexical_score(query_tokens: list[str], document: str, metadata: dict[str, Any]) -> float:
    if not query_tokens:
        return 0.0
    text = " ".join([document, " ".join(str(value) for value in metadata.values())]).lower()
    document_tokens = _tokens(text)
    if not document_tokens:
        return 0.0
    token_counts: dict[str, int] = {}
    for token in document_tokens:
        token_counts[token] = token_counts.get(token, 0) + 1
    unique_query_tokens = set(query_tokens)
    overlap = sum(1 for token in unique_query_tokens if token in token_counts)
    frequency = sum(min(token_counts.get(token, 0), 3) for token in unique_query_tokens)
    phrase_bonus = 0.0
    lowered_query = " ".join(query_tokens)
    if lowered_query and lowered_query in text:
        phrase_bonus += 2.0
    if len(unique_query_tokens) >= 3:
        bigrams = zip(query_tokens, query_tokens[1:])
        phrase_bonus += sum(0.35 for left, right in bigrams if f"{left} {right}" in text)
    length_penalty = 1.0 + (len(document_tokens) / 1200.0)
    return ((overlap * 1.5) + (frequency * 0.25) + phrase_bonus) / length_penalty
