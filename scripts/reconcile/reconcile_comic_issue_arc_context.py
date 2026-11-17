"""Verify inventoried comic references against the released corpus and arc map."""

import collections
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
ISSUES = "catalog/works/comics-issue-inventory.json"
ARCS = "catalog/works/comics-arc-inventory.json"
CORPUS = "unified/corpus.parquet"
ARC_LAYER = "data/wookieepedia-kotor-series-arc-sections.jsonl"
REFERENCE_FIELDS = (
    "secondary_summary",
    "reviewed_plot_section",
    "publication_introduction",
    "reviewed_publication_introduction",
    "appearance_index",
)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def reconcile(root):
    manifest = json.loads((root / "manifest.json").read_text())
    expected = {entry["path"]: entry["sha256"] for entry in manifest["input_files"]}
    hashes = {path: sha256(root / path) for path in [ISSUES, ARCS, CORPUS, ARC_LAYER]}
    for path, digest in hashes.items():
        if expected.get(path) != digest:
            raise ValueError(f"Manifest mismatch: {path}")

    issues = json.loads((root / ISSUES).read_text())["issues"]
    arcs = json.loads((root / ARCS).read_text())["arcs"]
    records = collections.defaultdict(list)
    columns = [
        "source_layer",
        "source_row",
        "text_sha256",
        "source_url",
        "source_metadata_json",
        "text",
    ]
    for batch in pq.ParquetFile(root / CORPUS).iter_batches(columns=columns):
        for record in batch.to_pylist():
            if (
                hashlib.sha256(record.pop("text").encode()).hexdigest()
                != record["text_sha256"]
            ):
                raise ValueError("Corpus text hash mismatch")
            records[(record["source_layer"], record["text_sha256"])].append(record)

    def resolve(reference, work_id):
        layer = reference["dataset"]
        digest = reference.get("text_sha256") or reference.get("sha256")
        matches = records[(layer, digest)]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one released record for {work_id}: {layer}, {digest}"
            )
        record = matches[0]
        metadata = json.loads(record["source_metadata_json"])
        revision = reference.get("revision_id")
        if revision is not None and str(metadata.get("revision_id")) != str(revision):
            raise ValueError(f"Revision mismatch for {work_id}: {layer}")
        return {
            "dataset": layer,
            "source_row": record["source_row"],
            "text_sha256": digest,
            "source_url": record["source_url"],
        }

    arc_lookup = collections.defaultdict(list)
    arc_records = {}
    with (root / ARC_LAYER).open() as stream:
        for row, line in enumerate(stream):
            record = json.loads(line)
            key = record["inventory_arc_id"]
            if key in arc_records:
                raise ValueError(f"Duplicate arc section: {key}")
            arc_records[key] = (row, record)
    for arc in arcs:
        for work_id in arc["issue_ids"]:
            arc_lookup[work_id].append(arc)

    rows = []
    series_counts = collections.defaultdict(collections.Counter)
    for issue in issues:
        work_id = issue["work_id"]
        verified = {}
        pending = {}
        for field in REFERENCE_FIELDS:
            reference = issue.get(field)
            if not reference:
                continue
            if "dataset" not in reference:
                pending[field] = reference
                continue
            verified[field] = resolve(reference, work_id)
        contexts = []
        for arc in arc_lookup[work_id]:
            context = {
                "arc_id": arc["id"],
                "arc_title": arc["title"],
                "arc_issue_mapping_source": ARCS,
            }
            if "series_plot_section" in arc:
                row, record = arc_records[arc["id"]]
                reference = arc["series_plot_section"]
                digest = reference["text_sha256"]
                if (
                    hashlib.sha256(record["text"].encode()).hexdigest() != digest
                    or work_id not in record["issue_ids"]
                ):
                    raise ValueError(f"Arc context mismatch: {work_id}")
                released = resolve({"dataset": ARC_LAYER, **reference}, work_id)
                if released["source_row"] != row:
                    raise ValueError(f"Arc row mismatch: {work_id}")
                context["secondary_arc_context"] = {
                    **released,
                    "section": record["section"],
                    "revision_id": record["revision_id"],
                }
            contexts.append(context)
        summary = any(
            field in verified
            for field in ["reviewed_plot_section", "secondary_summary"]
        )
        publication = any(
            field in verified
            for field in [
                "publication_introduction",
                "reviewed_publication_introduction",
            ]
        )
        primary = issue["primary_content"] != "not_acquired"
        if primary:
            raise ValueError(f"Primary acquisition evidence requires review: {work_id}")
        rows.append(
            {
                "work_id": work_id,
                "title": issue.get("title")
                or issue["series"] + " " + str(issue["issue_number"]),
                "series": issue["series"],
                "issue_level_secondary_summary_present": summary,
                "publication_introduction_present": publication,
                "appearance_index_present": "appearance_index" in verified,
                "verified_references": verified,
                "pending_references": pending,
                "arc_contexts": contexts,
                "primary_content_acquired": primary,
                "permission_to_redistribute": issue["permission_to_redistribute"],
            }
        )
        group = series_counts[issue["series"]]
        group["issues"] += 1
        group["with_issue_level_secondary_summary"] += int(summary)
        group["with_publication_introduction"] += int(publication)
        group["with_appearance_index"] += int("appearance_index" in verified)

    missing = [row for row in rows if not row["issue_level_secondary_summary_present"]]
    counts = {
        "issues": len(rows),
        "with_verified_issue_level_secondary_summary": len(rows) - len(missing),
        "with_verified_publication_introduction": sum(
            row["publication_introduction_present"] for row in rows
        ),
        "with_verified_appearance_index": sum(
            row["appearance_index_present"] for row in rows
        ),
        "primary_content_acquired": sum(
            row["primary_content_acquired"] for row in rows
        ),
        "without_issue_level_secondary_summary": len(missing),
        "without_issue_summary_but_with_arc_mapping": sum(
            bool(row["arc_contexts"]) for row in missing
        ),
        "without_issue_summary_but_with_arc_text": sum(
            any("secondary_arc_context" in arc for arc in row["arc_contexts"])
            for row in missing
        ),
        "without_issue_summary_or_arc_text": sum(
            not any("secondary_arc_context" in arc for arc in row["arc_contexts"])
            for row in missing
        ),
    }
    report = {
        "scope": "Current inventoried comic issue references verified by exact text hash and revision against released corpus records. Summary, introduction, appearance and arc coverage are reported individually. Inventory completeness, story accuracy, original pages and rights remain unresolved.",
        "source_hashes": hashes,
        "counts": counts,
        "series": dict(sorted(series_counts.items())),
        "items": rows,
    }
    output = root / "evaluation/comic-issue-arc-context.json"
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(output)
    print(json.dumps(counts))


if __name__ == "__main__":
    reconcile(ROOT)
