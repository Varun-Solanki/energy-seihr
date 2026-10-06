from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from rag.vector_store import ChromaEvidenceStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the EPIGRID Chroma evidence index.")
    parser.add_argument("query")
    parser.add_argument("--collection", default="epigrid_evidence")
    parser.add_argument("--country", help="Optional ISO3 metadata filter, e.g. IND")
    parser.add_argument("--region", help="Optional region metadata filter")
    parser.add_argument("--source-id", help="Optional source_id metadata filter")
    parser.add_argument("--chunk-type", help="Optional chunk_type metadata filter")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--vector-only", action="store_true", help="Use raw vector search without lexical reranking")
    args = parser.parse_args()

    where = {}
    if args.country:
        where["country_iso3"] = args.country.upper()
    if args.region:
        where["region"] = args.region
    if args.source_id:
        where["source_id"] = args.source_id
    if args.chunk_type:
        where["chunk_type"] = args.chunk_type
    if len(where) > 1:
        where = {"$and": [{key: value} for key, value in where.items()]}

    store = ChromaEvidenceStore(persist_dir=settings.chroma_persist_dir, collection_name=args.collection)
    results = store.query(args.query, n_results=args.limit, where=where or None, hybrid=not args.vector_only)
    for index, result in enumerate(results, start=1):
        source = result.metadata.get("source_id", "unknown")
        region = result.metadata.get("region", "")
        period = result.metadata.get("period", "")
        score = f"{result.score:.3f}" if result.score is not None else "n/a"
        print(f"{index}. score={score} source={source} region={region} period={period}")
        print(f"   {result.content[:500]}")


if __name__ == "__main__":
    main()
