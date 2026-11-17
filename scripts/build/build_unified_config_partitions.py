"""Derive source-preserving Parquet views from the unified corpus.

Build and validate every partition in scratch space before replacing released
files. Publish the checksum index last so interrupted promotion is detectable.
"""

import collections
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build_partitions(root):
    manifest = json.loads((root / "manifest.json").read_text())
    sources = {
        entry["path"]
        for entry in manifest["input_files"]
        if entry["path"].startswith("data/") and entry["path"].endswith(".jsonl")
    }
    filenames = {source: Path(source).stem + ".parquet" for source in sources}
    if len(set(filenames.values())) != len(filenames):
        raise ValueError("Source layers have conflicting partition filenames")

    source_path = root / "unified/corpus.parquet"
    coverage = json.loads((root / "unified/coverage.json").read_text())
    if sha256(source_path) != coverage["output_sha256"]:
        raise ValueError("Unified corpus hash differs from coverage receipt")
    corpus = pq.ParquetFile(source_path)
    output = root / "unified/configs"
    output.mkdir(parents=True, exist_ok=True)
    counts = collections.Counter()
    writers = {}

    with TemporaryDirectory(prefix=".partitions-", dir=output.parent) as scratch:
        staging = Path(scratch)
        try:
            for batch in corpus.iter_batches(batch_size=256):
                grouped = collections.defaultdict(list)
                for row in batch.to_pylist():
                    if row["source_layer"] in sources:
                        grouped[row["source_layer"]].append(row)
                for source, rows in grouped.items():
                    if source not in writers:
                        writers[source] = pq.ParquetWriter(
                            staging / filenames[source],
                            corpus.schema_arrow,
                            compression="zstd",
                        )
                    writers[source].write_table(
                        pa.Table.from_pylist(rows, schema=corpus.schema_arrow)
                    )
                    counts[source] += len(rows)
        finally:
            for writer in writers.values():
                writer.close()

        if set(counts) != sources:
            raise ValueError(
                f"Missing source partitions: {sorted(sources - counts.keys())}"
            )
        for source in sources:
            if counts[source] != coverage["layers"][source]:
                raise ValueError(f"Partition row count mismatch: {source}")

        # Retain released bytes when only global corpus batch boundaries moved.
        unchanged = set()
        for source in sorted(sources):
            existing = output / filenames[source]
            staged = staging / filenames[source]
            if existing.is_file() and pq.read_table(existing).equals(
                pq.read_table(staged)
            ):
                unchanged.add(source)

        index = {
            "unified_sha256": coverage["output_sha256"],
            "partitions": {
                source: {
                    "path": "unified/configs/" + filenames[source],
                    "rows": counts[source],
                    "sha256": sha256(
                        (output if source in unchanged else staging) / filenames[source]
                    ),
                }
                for source in sorted(sources)
            },
        }
        index_path = staging / "configs.json"
        index_path.write_text(json.dumps(index, indent=2) + "\n")
        for source in sorted(sources):
            if source not in unchanged:
                (staging / filenames[source]).replace(output / filenames[source])
        index_path.replace(root / "unified/configs.json")
    print("Partitions", len(sources), "rows", sum(counts.values()))


if __name__ == "__main__":
    build_partitions(Path(__file__).resolve().parents[2])
