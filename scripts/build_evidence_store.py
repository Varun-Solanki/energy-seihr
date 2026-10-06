from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import BASE_DIR
from rag.evidence_store import EvidenceStoreBuilder


def main() -> None:
    parser = argparse.ArgumentParser(description="Build metadata-rich evidence chunks from normalized records.")
    parser.add_argument("--country", default="IND", help="ISO3 country code, e.g. IND")
    parser.add_argument("--input", help="Input normalized JSONL path")
    parser.add_argument("--output", help="Output evidence JSONL path")
    parser.add_argument("--chunk-words", type=int, default=700, help="Approximate words per document chunk")
    parser.add_argument("--overlap-words", type=int, default=90, help="Document chunk overlap in words")
    args = parser.parse_args()

    country = args.country.lower()
    input_path = Path(args.input) if args.input else BASE_DIR / "data" / "processed" / f"{country}_normalized_records.jsonl"
    output_path = Path(args.output) if args.output else BASE_DIR / "data" / "processed" / f"{country}_evidence_chunks.jsonl"
    if not input_path.is_absolute():
        input_path = BASE_DIR / input_path
    if not output_path.is_absolute():
        output_path = BASE_DIR / output_path

    result = EvidenceStoreBuilder(
        input_path=input_path,
        output_path=output_path,
        document_chunk_words=args.chunk_words,
        document_overlap_words=args.overlap_words,
    ).build()

    print(f"Evidence chunks written: {result.chunk_count}")
    print(f"Output: {result.output_path}")
    print(f"Manifest: {result.manifest_path}")
    print("Counts by type:")
    for key, count in result.counts_by_type.items():
        print(f"  {key}: {count}")
    print("Counts by source:")
    for key, count in result.counts_by_source.items():
        print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
