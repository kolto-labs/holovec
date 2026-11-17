"""Catalogue observed journal structure and exact dialogue quest references."""

import hashlib
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .dialogue_inventory import (
    encoded,
    graph_list,
    metadata_statistics,
    reader_signatures,
    structure_metadata,
    verify_source_indices,
)
from .game_inventory import SCHEMA as RESOURCE_SCHEMA
from .game_inventory import file_snapshot, sha256

JOURNAL_SCHEMA = RESOURCE_SCHEMA.append(pa.field("resource_sha256", pa.string()))
for name, kind in [
    ("journal_id", pa.string()),
    ("categories", pa.int64()),
    ("entries", pa.int64()),
    ("fields_json", pa.string()),
]:
    JOURNAL_SCHEMA = JOURNAL_SCHEMA.append(pa.field(name, kind))

REFERENCE_SCHEMA = pa.schema(
    [
        ("dialogue_id", pa.string()),
        ("node_kind", pa.string()),
        ("node_index", pa.int64()),
        ("field_index", pa.int64()),
        ("quest_tag_sha256", pa.string()),
        ("quest_entry", pa.int64()),
        ("matching_categories", pa.list_(pa.string())),
        ("matching_entries", pa.list_(pa.string())),
    ]
)


def binary_journal(body):
    """Read physical field signatures, category lists and entry IDs independently."""
    header = struct.unpack_from("<4s4s12I", body)
    if header[:2] != (b"JRL ", b"V3.2"):
        raise ValueError("Expected binary JRL V3.2")
    (
        struct_offset,
        struct_count,
        field_offset,
        field_count,
        label_offset,
        label_count,
    ) = header[2:8]
    field_indices, list_indices = header[10], header[12]

    def fields(index):
        if not 0 <= index < struct_count:
            raise ValueError("Invalid journal struct index")
        struct_id, data, count = struct.unpack_from(
            "<III", body, struct_offset + index * 12
        )
        if struct_id == 0xFFFFFFFF:
            struct_id = -1
        if count == 0:
            return struct_id, []
        indices = (
            [data]
            if count == 1
            else struct.unpack_from(f"<{count}I", body, field_indices + data)
        )
        result = []
        for field_index in indices:
            if field_index >= field_count:
                raise ValueError("Invalid journal field index")
            kind, label_index, value = struct.unpack_from(
                "<III", body, field_offset + field_index * 12
            )
            if label_index >= label_count:
                raise ValueError("Invalid journal label index")
            label = (
                body[
                    label_offset + label_index * 16 : label_offset
                    + (label_index + 1) * 16
                ]
                .split(b"\0", 1)[0]
                .decode("ascii")
            )
            result.append((label, kind, value))
        return struct_id, result

    def children(value):
        count = struct.unpack_from("<I", body, list_indices + value)[0]
        return struct.unpack_from(f"<{count}I", body, list_indices + value + 4)

    def named_list(index, label):
        matches = [
            (kind, value) for name, kind, value in fields(index)[1] if name == label
        ]
        if len(matches) != 1 or matches[0][0] != 15:
            raise ValueError(f"Expected one journal list {label}")
        return children(matches[0][1])

    signatures = Counter()

    def visit(index, ancestors):
        if index in ancestors:
            raise ValueError("Cyclic journal struct references")
        struct_id, values = fields(index)
        signatures[(struct_id, tuple((label, kind) for label, kind, _ in values))] += 1
        for _, kind, value in values:
            if kind == 14:
                visit(value, ancestors | {index})
            elif kind == 15:
                for child in children(value):
                    visit(child, ancestors | {index})

    visit(0, set())
    category_entries = []
    for category in named_list(0, "Categories"):
        entry_ids = []
        for entry in named_list(category, "EntryList"):
            matches = [
                (kind, value)
                for label, kind, value in fields(entry)[1]
                if label == "ID"
            ]
            if len(matches) != 1 or matches[0][0] != 4:
                raise ValueError("Expected one UInt32 journal entry ID")
            entry_ids.append(matches[0][1])
        category_entries.append(entry_ids)
    return signatures, category_entries


def field_value(metadata, label, kind):
    values = [
        field["value"]
        for field in metadata["fields"]
        if field["label"] == label and field["type"] == kind
    ]
    return values[0] if len(values) == 1 else None


def journal_categories(metadata):
    categories = field_value(metadata, "Categories", "List")
    if not isinstance(categories, list):
        raise TypeError("Expected a journal Categories list")
    return categories


def journal_entry_ids(category):
    entries = field_value(category, "EntryList", "List")
    if not isinstance(entries, list):
        raise TypeError("Expected a journal EntryList")
    values = [field_value(entry, "ID", "UInt32") for entry in entries]
    if any(value is None for value in values):
        raise ValueError("Expected unique journal entry ID fields")
    return values


def loose_journals(installation, game, inventory_id):
    files = file_snapshot(installation)
    files.update(
        {
            path: path.stat()
            for path in installation.iterdir()
            if path.is_file() and path.suffix.casefold() == ".jrl"
        }
    )
    rows, snapshots = [], {}
    for path, info in sorted(files.items()):
        if path.suffix.casefold() != ".jrl":
            continue
        snapshots[path] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        rows.append(
            {
                "game": game,
                "inventory_id": inventory_id,
                "storage": "loose",
                "container": path.relative_to(installation).as_posix(),
                "source_entry": 0,
                "resref": path.stem,
                "resource_type": "jrl",
                "resource_type_id": 2056,
                "offset": 0,
                "size": info.st_size,
                "resource_sha256": sha256(path),
            }
        )
    return rows, snapshots


def dialogue_references(journals, dialogue_games, nodes_path):
    categories, entries = defaultdict(list), defaultdict(list)
    for journal in journals:
        for index, category in enumerate(
            journal_categories(json.loads(journal["fields_json"]))
        ):
            tag = field_value(category, "Tag", "String")
            if tag is None or not tag["characters"]:
                continue
            identity = journal["journal_id"] + "/" + str(index)
            key = (journal["game"], tag["decoded_utf8_sha256"])
            categories[key].append(identity)
            for entry_index, entry_id in enumerate(journal_entry_ids(category)):
                entries[(*key, entry_id)].append(identity + "/" + str(entry_index))
    rows, counts = [], Counter()
    for batch in pq.ParquetFile(nodes_path).iter_batches(batch_size=256):
        for node in batch.to_pylist():
            game = dialogue_games[node["dialogue_id"]]
            metadata = json.loads(node["fields_json"])
            quest_entry = field_value(metadata, "QuestEntry", "UInt32")
            counts["nodes_inspected"] += 1
            for index, field in enumerate(metadata["fields"]):
                if field["label"] != "Quest" or field["type"] != "String":
                    continue
                if not field["value"]["characters"]:
                    counts["empty_quest_fields"] += 1
                    continue
                digest = field["value"]["decoded_utf8_sha256"]
                key = (game, digest)
                matches = categories[key]
                entry_matches = entries[(*key, quest_entry)]
                rows.append(
                    {
                        "dialogue_id": node["dialogue_id"],
                        "node_kind": node["node_kind"],
                        "node_index": node["node_index"],
                        "field_index": index,
                        "quest_tag_sha256": digest,
                        "quest_entry": quest_entry,
                        "matching_categories": matches,
                        "matching_entries": entry_matches,
                    }
                )
                counts["nonempty_quest_fields"] += 1
                counts["with_exact_category_matches"] += bool(matches)
                counts["with_exact_entry_matches"] += bool(entry_matches)
    return rows, dict(counts)


def inventory_journals(root, installations, output):
    from pykotor.resource.formats.gff import read_gff

    inputs = [
        "catalog/games/resources.parquet",
        "catalog/games/resource-census.json",
        "catalog/games/dialogues.parquet",
        "catalog/games/dialogue-nodes.parquet",
    ]
    manifest = json.loads((root / "manifest.json").read_text())
    pins = {item["path"]: item["sha256"] for item in manifest["input_files"]}
    for relative in inputs:
        if sha256(root / relative) != pins[relative]:
            raise ValueError(f"Journal input differs from manifest: {relative}")
    census = json.loads((root / inputs[1]).read_text())
    games = {item["game"]: item for item in census["installations"]}
    selected_games = dict(installations)
    if (
        not selected_games
        or len(selected_games) != len(installations)
        or set(selected_games) != set(games)
    ):
        raise ValueError("Supply each game identifier from the resource census once")
    resources = pq.read_table(
        root / inputs[0], filters=[("resource_type", "=", "jrl")]
    ).to_pylist()
    journals, loose_sources, game_counts = [], [], {}
    for game, location in installations:
        installation = Path(location).resolve(strict=True)
        packed = [row for row in resources if row["game"] == game]
        snapshots = verify_source_indices(game, installation, packed, games[game])
        loose, loose_snapshots = loose_journals(
            installation, game, games[game]["inventory_id"]
        )
        snapshots.update(loose_snapshots)
        loose_sources.extend(loose)
        counts = Counter(packed_resources=len(packed), loose_resources=len(loose))
        for resource in sorted(
            packed + loose, key=lambda row: (row["container"], row["source_entry"])
        ):
            with (installation / resource["container"]).open("rb") as stream:
                stream.seek(resource["offset"])
                body = stream.read(resource["size"])
            if len(body) != resource["size"]:
                raise ValueError("Truncated journal payload")
            digest = hashlib.sha256(body).hexdigest()
            if resource["storage"] == "loose" and digest != resource["resource_sha256"]:
                raise ValueError("Loose journal changed after its snapshot")
            graph = read_gff(body)
            metadata = structure_metadata(graph.root)
            categories = graph_list(graph.root, "Categories")
            signatures, binary_ids = binary_journal(body)
            observed_ids = [
                journal_entry_ids(category) for category in journal_categories(metadata)
            ]
            if (
                signatures != reader_signatures(graph.root)
                or binary_ids != observed_ids
            ):
                raise ValueError(
                    "Journal reader differs from independent binary observations"
                )
            row = {
                **resource,
                "resource_sha256": digest,
                "journal_id": resource["inventory_id"]
                + "/"
                + resource["container"]
                + "#"
                + str(resource["source_entry"]),
                "categories": len(categories),
                "entries": sum(map(len, binary_ids)),
                "fields_json": encoded(metadata),
            }
            journals.append(row)
            counts.update(categories=row["categories"], entries=row["entries"])
        for path, before in snapshots.items():
            info = path.stat()
            if before != (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns):
                raise ValueError("Journal source changed during extraction")
        if loose_journals(installation, game, games[game]["inventory_id"]) != (
            loose,
            loose_snapshots,
        ):
            raise ValueError("Loose journal population changed during extraction")
        game_counts[game] = dict(counts)
    dialogue_games = {
        row["dialogue_id"]: row["game"]
        for row in pq.read_table(
            root / inputs[2], columns=["dialogue_id", "game"]
        ).to_pylist()
    }
    references, reference_counts = dialogue_references(
        journals, dialogue_games, root / inputs[3]
    )
    output.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for name, records, schema in [
        ("journals", journals, JOURNAL_SCHEMA),
        ("journal-dialogue-references", references, REFERENCE_SCHEMA),
    ]:
        path = output / (name + ".parquet")
        temporary = path.with_suffix(".parquet.tmp")
        pq.write_table(
            pa.Table.from_pylist(records, schema=schema),
            temporary,
            compression="zstd",
            write_statistics=False,
        )
        temporary.replace(path)
        outputs[name] = {
            "file": path.name,
            "rows": len(records),
            "sha256": sha256(path),
        }
    receipt = {
        "scope": "Every indexed JRL resource and observed loose .jrl file under inventoried asset directories and the installation root. Physical metadata, source occurrences and duplicate fields are retained. String and localized prose have fingerprints.",
        "limitations": "Exact case-sensitive quest-tag fingerprint and entry-ID joins are candidate references. Module and override precedence, script-generated updates, state-dependent behavior, narrative prose, other builds and languages remain unresolved.",
        "input_sha256": {relative: pins[relative] for relative in inputs},
        "producer_sha256": sha256(Path(__file__)),
        "metadata_reader_sha256": sha256(
            Path(__file__).with_name("dialogue_inventory.py")
        ),
        "reader_module_sha256": {
            name: sha256(Path(module.__file__))
            for name, module in sorted(sys.modules.copy().items())
            if name.startswith(("pykotor.", "utility."))
            and getattr(module, "__file__", None)
            and Path(module.__file__).is_file()
        },
        "independent_validation": "All physical GFF struct/field signatures, category and entry-list counts and ordered UInt32 entry IDs cross-checked directly against binary tables.",
        "source_containers_stable": True,
        "loose_resources": loose_sources,
        "games": game_counts,
        "dialogue_references": reference_counts,
        "outputs": outputs,
        "embedded": False,
    }
    (output / "journal-census.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps({"games": game_counts, "dialogue_references": reference_counts}),
        flush=True,
    )


def verify_journals(root, directory=None):
    released = directory is None
    directory = directory or root / "catalog/games"
    receipt = json.loads((directory / "journal-census.json").read_text())
    for relative, digest in receipt["input_sha256"].items():
        if sha256(root / relative) != digest:
            raise ValueError(f"Stale journal input: {relative}")
    tables = {}
    schemas = {
        "journals": JOURNAL_SCHEMA,
        "journal-dialogue-references": REFERENCE_SCHEMA,
    }
    for name, specification in receipt["outputs"].items():
        path = directory / specification["file"]
        if sha256(path) != specification["sha256"]:
            raise ValueError(f"Changed journal output: {name}")
        table = pq.read_table(path)
        if table.num_rows != specification["rows"] or table.schema != schemas[name]:
            raise ValueError(f"Journal schema or row count mismatch: {name}")
        tables[name] = table.to_pylist()
    resources = pq.read_table(
        root / "catalog/games/resources.parquet",
        filters=[("resource_type", "=", "jrl")],
    ).to_pylist()
    expected = resources + receipt["loose_resources"]
    loose_sources = {
        (row["game"], row["container"]): row for row in receipt["loose_resources"]
    }
    observed = [
        {key: row[key] for key in RESOURCE_SCHEMA.names} for row in tables["journals"]
    ]
    if sorted(map(encoded, observed)) != sorted(
        encoded({key: row[key] for key in RESOURCE_SCHEMA.names}) for row in expected
    ):
        raise ValueError("Journal resources differ from the packed and loose census")
    counts = {
        game: Counter(packed_resources=0, loose_resources=0, categories=0, entries=0)
        for game in receipt["games"]
    }
    seen = set()
    for row in tables["journals"]:
        if row["storage"] == "loose":
            source = loose_sources[(row["game"], row["container"])]
            if row["resource_sha256"] != source["resource_sha256"]:
                raise ValueError("Loose journal payload fingerprint mismatch")
        identity = (
            row["inventory_id"]
            + "/"
            + row["container"]
            + "#"
            + str(row["source_entry"])
        )
        if row["journal_id"] != identity or identity in seen:
            raise ValueError("Invalid or repeated journal identity")
        seen.add(identity)
        metadata = json.loads(row["fields_json"])
        metadata_statistics(metadata)
        categories = journal_categories(metadata)
        entries = sum(len(journal_entry_ids(category)) for category in categories)
        if row["categories"] != len(categories) or row["entries"] != entries:
            raise ValueError("Journal category or entry count mismatch")
        counts[row["game"]].update(categories=len(categories), entries=entries)
        counts[row["game"]][
            "loose_resources" if row["storage"] == "loose" else "packed_resources"
        ] += 1
    if {game: dict(count) for game, count in counts.items()} != receipt["games"]:
        raise ValueError("Journal game totals mismatch")
    dialogue_games = {
        row["dialogue_id"]: row["game"]
        for row in pq.read_table(
            root / "catalog/games/dialogues.parquet", columns=["dialogue_id", "game"]
        ).to_pylist()
    }
    references, reference_counts = dialogue_references(
        tables["journals"],
        dialogue_games,
        root / "catalog/games/dialogue-nodes.parquet",
    )
    if (
        references != tables["journal-dialogue-references"]
        or reference_counts != receipt["dialogue_references"]
    ):
        raise ValueError("Journal dialogue references differ from source nodes")
    if released:
        manifest = json.loads((root / "manifest.json").read_text())
        totals = {
            "game_journal_resources": len(tables["journals"]),
            "game_journal_category_occurrences": sum(
                row["categories"] for row in tables["journals"]
            ),
            "game_journal_entry_occurrences": sum(
                row["entries"] for row in tables["journals"]
            ),
            "game_journal_dialogue_references": len(references),
        }
        for name, count in totals.items():
            if manifest["counts"].get(name) != count:
                raise ValueError(f"Journal manifest count mismatch: {name}")
