"""Build a source-preserving, non-embedded view of every manifest text layer.

Original layers remain authoritative. Each row includes its source path, row
number, complete text, and remaining source metadata serialized as JSON; no
deduplication, model call or external processing is performed.
"""

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
manifest = json.loads((ROOT / "manifest.json").read_text())
entries = [
    x
    for x in manifest["input_files"]
    if x["path"].startswith("data/")
    and Path(x["path"]).suffix in (".jsonl", ".parquet")
]
conflict_path = ROOT / "catalog/sources/source-conflicts.json"
conflict_bytes = conflict_path.read_bytes()
conflict_entry = next(
    entry
    for entry in manifest["input_files"]
    if entry["path"] == "catalog/sources/source-conflicts.json"
)
if hashlib.sha256(conflict_bytes).hexdigest() != conflict_entry["sha256"]:
    raise ValueError("Conflict registry hash mismatch")
conflicts = json.loads(conflict_bytes)["conflicts"]
schema = pa.schema(
    [
        ("record_id", pa.string()),
        ("source_layer", pa.string()),
        ("source_row", pa.int64()),
        ("title", pa.string()),
        ("source_url", pa.string()),
        ("license", pa.string()),
        ("continuity", pa.string()),
        ("text", pa.string()),
        ("text_sha256", pa.string()),
        ("source_warnings", pa.list_(pa.string())),
        ("source_metadata_json", pa.large_string()),
    ]
)
output = ROOT / "unified/corpus.parquet"
output.parent.mkdir(exist_ok=True)
temporary_path = output.with_suffix(".parquet.tmp")
counts = {}
nontext_counts = {}
buffer = []


def flush(writer):
    if buffer:
        writer.write_table(pa.Table.from_pylist(buffer, schema=schema))
        buffer.clear()


def records(path):
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    yield json.loads(line)
    else:
        for batch in pq.ParquetFile(path).iter_batches(batch_size=128):
            yield from batch.to_pylist()


def clean(value):
    return value if isinstance(value, str) else None


try:
    with pq.ParquetWriter(temporary_path, schema, compression="zstd") as writer:
        for entry in entries:
            path = ROOT / entry["path"]
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != entry["sha256"]:
                raise ValueError("Manifest hash mismatch: " + entry["path"])
            retained = 0
            nontext_count = 0
            for row_number, record in enumerate(records(path)):
                if record.get("evidence_class") == "secondary_technical_documentation":
                    raise ValueError(
                        "Software project documentation is outside the corpus boundary: "
                        + entry["path"]
                    )
                text = record.get("text")
                if not isinstance(text, str) or not text.strip():
                    nontext_count += 1
                    continue
                metadata = {k: v for k, v in record.items() if k != "text"}
                source_url = record.get("url") or record.get("source_url")
                text_hash = hashlib.sha256(text.encode()).hexdigest()
                warnings = [
                    conflict["warning"]
                    for conflict in conflicts
                    if conflict["source_url"] == source_url
                    and conflict.get("source_text_sha256") == text_hash
                ]
                buffer.append(
                    {
                        "record_id": entry["path"] + "#" + str(row_number),
                        "source_layer": entry["path"],
                        "source_row": row_number,
                        "title": clean(record.get("title")),
                        "source_url": clean(source_url),
                        "license": clean(
                            record.get("license") or record.get("license_spdx")
                        ),
                        "continuity": clean(record.get("continuity")),
                        "text": text,
                        "text_sha256": text_hash,
                        "source_warnings": warnings,
                        "source_metadata_json": json.dumps(
                            metadata, ensure_ascii=False, sort_keys=True, default=str
                        ),
                    }
                )
                retained += 1
                if len(buffer) >= 256:
                    flush(writer)
            counts[entry["path"]] = retained
            if nontext_count:
                nontext_counts[entry["path"]] = nontext_count
        flush(writer)
    temporary_path.replace(output)
except BaseException:
    if temporary_path.exists():
        temporary_path.unlink()
    raise
with output.open("rb") as stream:
    digest = hashlib.file_digest(stream, "sha256").hexdigest()
audit = {
    "description": "Unified view retains each nonempty text record and source metadata; duplicate and overlapping sources remain distinct. Excluded empty/non-text rows are reported. It is not a complete lore corpus.",
    "layers": counts,
    "input_layer_sha256": {entry["path"]: entry["sha256"] for entry in entries},
    "source_conflicts_sha256": hashlib.sha256(conflict_bytes).hexdigest(),
    "empty_or_nontext_rows": nontext_counts,
    "rows": sum(counts.values()),
    "output_sha256": digest,
    "embedded": False,
}
(ROOT / "unified/coverage.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False) + "\n"
)
print(
    "Unified",
    len(counts),
    "layers",
    sum(counts.values()),
    "rows; empty or nontext",
    sum(nontext_counts.values()),
    "sha256",
    digest,
)
