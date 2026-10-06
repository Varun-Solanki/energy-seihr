from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import BASE_DIR, settings
from rag.vector_store import ChromaEvidenceStore, read_evidence_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Index EPIGRID evidence chunks into Chroma.")
    parser.add_argument("--country", default="IND", help="ISO3 country code, e.g. IND")
    parser.add_argument("--input", help="Evidence chunks JSONL path")
    parser.add_argument("--collection", default="epigrid_evidence", help="Chroma collection name")
    parser.add_argument("--reset", action="store_true", help="Delete and rebuild the collection first")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    country = args.country.lower()
    input_path = Path(args.input) if args.input else BASE_DIR / "data" / "processed" / f"{country}_evidence_chunks.jsonl"
    if not input_path.is_absolute():
        input_path = BASE_DIR / input_path

    store = ChromaEvidenceStore(persist_dir=settings.chroma_persist_dir, collection_name=args.collection)
    if args.reset:
        store.reset_collection()
    indexed = store.index_chunks(read_evidence_chunks(input_path), batch_size=args.batch_size)

    print(f"Indexed chunks: {indexed}")
    print(f"Collection count: {store.count()}")
    print(f"Collection: {args.collection}")
    print(f"Persist dir: {settings.chroma_persist_dir}")


if __name__ == "__main__":
    main()
