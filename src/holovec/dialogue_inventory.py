"""Inventory observed conversation graphs while withholding prose and binaries."""

import hashlib
import json
import math
import struct
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .game_inventory import SCHEMA as RESOURCE_SCHEMA
from .game_inventory import file_snapshot, sha256

LOOSE_SCHEMA = RESOURCE_SCHEMA.append(pa.field("resource_sha256", pa.string()))


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def text_fingerprint(text):
    return {
        "characters": len(text),
        "decoded_utf8_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def finite(value):
    return value if math.isfinite(value) else {"nonfinite_float": value.hex()}


def structure_metadata(source, external_lists=()):
    """Retain physical field order and duplicates, including duplicate labels."""
    fields = []
    for label, kind, value in source:
        if label in external_lists:
            result = {"external_graph_list": label, "items": len(value)}
        elif kind.name == "String":
            result = {"withheld_text": True, **text_fingerprint(value)}
        elif kind.name == "LocalizedString":
            result = {
                "stringref": value.stringref,
                "substrings": [
                    {
                        "language": int(language),
                        "gender": int(gender),
                        **text_fingerprint(text),
                    }
                    for language, gender, text in value
                ],
            }
        elif kind.name == "ResRef":
            result = str(value)
        elif kind.name == "Binary":
            result = {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
        elif kind.name == "Struct":
            result = structure_metadata(value)
        elif kind.name == "List":
            result = [structure_metadata(item) for item in value]
        elif kind.name in {"Vector3", "Vector4"}:
            result = [finite(number) for number in value]
        elif isinstance(value, float):
            result = finite(value)
        elif isinstance(value, int):
            result = value
        else:
            raise ValueError(f"Unsupported GFF field type {kind.name}")
        fields.append({"label": label, "type": kind.name, "value": result})
    return {"struct_id": source.struct_id, "fields": fields}


def graph_list(source, label):
    matches = [(kind, value) for name, kind, value in source if name == label]
    if not matches:
        return []
    if len(matches) != 1 or matches[0][0].name != "List":
        raise ValueError(f"Ambiguous or mistyped graph list {label}")
    return matches[0][1]


def target_index(source):
    values = [value for label, _, value in source if label == "Index"]
    return values[0] if len(values) == 1 and isinstance(values[0], int) else None


def reader_signatures(source):
    signatures = Counter()
    signatures[
        (source.struct_id, tuple((label, int(kind)) for label, kind, _ in source))
    ] += 1
    for _, kind, value in source:
        if kind.name == "Struct":
            signatures.update(reader_signatures(value))
        elif kind.name == "List":
            for item in value:
                signatures.update(reader_signatures(item))
    return signatures


def wire_observations(body):
    """Independently read physical GFF tables, graph lists and edge indices."""
    header = struct.unpack_from("<4s4s12I", body)
    if header[:2] != (b"DLG ", b"V3.2"):
        raise ValueError("Expected binary DLG V3.2")
    so, sc, fo, fc, lo, lc, _, _, fio, _, lio, _ = header[2:]

    def fields(index):
        if not 0 <= index < sc:
            raise ValueError("Invalid raw GFF struct index")
        struct_id, data, count = struct.unpack_from("<III", body, so + index * 12)
        if struct_id == 0xFFFFFFFF:
            struct_id = -1
        if count == 0:
            return struct_id, []
        indices = (
            [data] if count == 1 else struct.unpack_from(f"<{count}I", body, fio + data)
        )
        result = []
        for item in indices:
            if item >= fc:
                raise ValueError("Invalid raw GFF field index")
            kind, label_index, value = struct.unpack_from("<III", body, fo + item * 12)
            if label_index >= lc:
                raise ValueError("Invalid raw GFF label index")
            label = (
                body[lo + label_index * 16 : lo + (label_index + 1) * 16]
                .split(b"\0", 1)[0]
                .decode("ascii")
            )
            result.append((label, kind, value))
        return struct_id, result

    def children(value):
        count = struct.unpack_from("<I", body, lio + value)[0]
        return struct.unpack_from(f"<{count}I", body, lio + value + 4)

    def get_list(index, label):
        matches = [
            (kind, value) for name, kind, value in fields(index)[1] if name == label
        ]
        if not matches:
            return ()
        if len(matches) != 1 or matches[0][0] != 15:
            raise ValueError(f"Ambiguous raw graph list {label}")
        return children(matches[0][1])

    def number(index):
        matches = [
            (kind, value) for name, kind, value in fields(index)[1] if name == "Index"
        ]
        if len(matches) != 1:
            return None
        kind, value = matches[0]
        formats = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i"}
        if kind not in formats:
            return None
        fmt = "<" + formats[kind]
        return struct.unpack(fmt, struct.pack("<I", value)[: struct.calcsize(fmt)])[0]

    signatures = Counter()

    def visit(index):
        struct_id, values = fields(index)
        signatures[(struct_id, tuple((label, kind) for label, kind, _ in values))] += 1
        for _, kind, value in values:
            if kind == 14:
                visit(value)
            elif kind == 15:
                for child in children(value):
                    visit(child)

    visit(0)
    entries, replies = get_list(0, "EntryList"), get_list(0, "ReplyList")
    links = [
        ("start", -1, i, "entry", number(link))
        for i, link in enumerate(get_list(0, "StartingList"))
    ]
    for source_kind, nodes, label, target_kind in [
        ("entry", entries, "RepliesList", "reply"),
        ("reply", replies, "EntriesList", "entry"),
    ]:
        for index, node in enumerate(nodes):
            links.extend(
                (source_kind, index, i, target_kind, number(link))
                for i, link in enumerate(get_list(node, label))
            )
    return len(entries), len(replies), links, signatures


def dialogue_records(resource, body):
    from pykotor.resource.formats.gff import read_gff

    graph = read_gff(body)
    entries = graph_list(graph.root, "EntryList")
    replies = graph_list(graph.root, "ReplyList")
    dialogue_id = (
        resource["inventory_id"]
        + "/"
        + resource["container"]
        + "#"
        + str(resource["source_entry"])
    )
    nodes, edges = [], []

    def append_edges(source_kind, source_index, links, target_kind):
        limit = len(entries) if target_kind == "entry" else len(replies)
        for index, link in enumerate(links):
            target = target_index(link)
            edges.append(
                {
                    "dialogue_id": dialogue_id,
                    "source_kind": source_kind,
                    "source_index": source_index,
                    "edge_index": index,
                    "target_kind": target_kind,
                    "target_index": target,
                    "target_valid": target is not None and 0 <= target < limit,
                    "fields_json": encoded(structure_metadata(link)),
                }
            )

    append_edges("start", -1, graph_list(graph.root, "StartingList"), "entry")
    for kind, values, link_label, target_kind in [
        ("entry", entries, "RepliesList", "reply"),
        ("reply", replies, "EntriesList", "entry"),
    ]:
        for index, node in enumerate(values):
            text_fields = [
                value
                for label, field_type, value in node
                if label == "Text" and field_type.name == "LocalizedString"
            ]
            text = text_fields[0] if len(text_fields) == 1 else None
            nodes.append(
                {
                    "dialogue_id": dialogue_id,
                    "node_kind": kind,
                    "node_index": index,
                    "text_stringref": text.stringref if text is not None else None,
                    "inline_localizations": len(list(text))
                    if text is not None
                    else None,
                    "potentially_reachable": False,
                    "fields_json": encoded(structure_metadata(node, {link_label})),
                }
            )
            append_edges(kind, index, graph_list(node, link_label), target_kind)

    wire_entries, wire_replies, wire_links, signatures = wire_observations(body)
    observed_links = [
        (
            e["source_kind"],
            e["source_index"],
            e["edge_index"],
            e["target_kind"],
            e["target_index"],
        )
        for e in edges
    ]
    if (wire_entries, wire_replies, wire_links) != (
        len(entries),
        len(replies),
        observed_links,
    ):
        raise ValueError("Raw GFF graph differs from library reader")
    if signatures != reader_signatures(graph.root):
        raise ValueError("Raw GFF field/struct signatures differ from library reader")

    reachable = reachable_nodes(edges)
    for node in nodes:
        node["potentially_reachable"] = (
            node["node_kind"],
            node["node_index"],
        ) in reachable
    summary = {
        key: resource[key]
        for key in [
            "game",
            "inventory_id",
            "container",
            "source_entry",
            "resref",
            "offset",
            "size",
        ]
    }
    summary.update(
        dialogue_id=dialogue_id,
        resource_sha256=hashlib.sha256(body).hexdigest(),
        entry_nodes=len(entries),
        reply_nodes=len(replies),
        starting_edges=sum(e["source_kind"] == "start" for e in edges),
        edges=len(edges),
        invalid_edges=sum(not e["target_valid"] for e in edges),
        unreachable_nodes=len(nodes) - len(reachable),
        physical_struct_occurrences=sum(signatures.values()),
        physical_field_occurrences=sum(
            len(signature[1]) * count for signature, count in signatures.items()
        ),
        fields_json=encoded(
            structure_metadata(graph.root, {"EntryList", "ReplyList", "StartingList"})
        ),
    )
    return summary, nodes, edges


def reachable_nodes(edges):
    adjacency = defaultdict(list)
    for edge in edges:
        if edge["target_valid"]:
            adjacency[(edge["source_kind"], edge["source_index"])].append(
                (edge["target_kind"], edge["target_index"])
            )
    pending = deque(adjacency[("start", -1)])
    reached = set()
    while pending:
        node = pending.popleft()
        if node not in reached:
            reached.add(node)
            pending.extend(adjacency[node])
    return reached


SCHEMAS = {
    "dialogues": pa.schema(
        [
            (key, pa.string())
            for key in [
                "game",
                "inventory_id",
                "dialogue_id",
                "container",
                "resref",
                "resource_sha256",
                "fields_json",
            ]
        ]
        + [
            (key, pa.int64())
            for key in [
                "source_entry",
                "offset",
                "size",
                "entry_nodes",
                "reply_nodes",
                "starting_edges",
                "edges",
                "invalid_edges",
                "unreachable_nodes",
                "physical_struct_occurrences",
                "physical_field_occurrences",
            ]
        ]
    ),
    "dialogue-nodes": pa.schema(
        [
            ("dialogue_id", pa.string()),
            ("node_kind", pa.string()),
            ("node_index", pa.int64()),
            ("text_stringref", pa.int64()),
            ("inline_localizations", pa.int64()),
            ("potentially_reachable", pa.bool_()),
            ("fields_json", pa.string()),
        ]
    ),
    "dialogue-edges": pa.schema(
        [
            ("dialogue_id", pa.string()),
            ("source_kind", pa.string()),
            ("source_index", pa.int64()),
            ("edge_index", pa.int64()),
            ("target_kind", pa.string()),
            ("target_index", pa.int64()),
            ("target_valid", pa.bool_()),
            ("fields_json", pa.string()),
        ]
    ),
}


def verify_source_indices(game, installation, resources, census):
    from pykotor.extract.capsule import LazyCapsule
    from pykotor.extract.chitin import Chitin

    selected = {r["container"] for r in resources}
    identity_files = {"chitin.key", *(table["file"] for table in census["talk_tables"])}
    snapshots = {}
    for relative in sorted(selected | identity_files):
        path = installation / relative
        info = path.stat()
        snapshots[path] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    observed = defaultdict(list)

    def append(resource):
        relative = Path(resource.filepath()).relative_to(installation).as_posix()
        if relative in selected:
            observed[relative].append(
                [
                    len(observed[relative]),
                    resource.resname(),
                    resource.restype().extension,
                    resource.restype().type_id,
                    resource.offset(),
                    resource.size(),
                ]
            )

    if sha256(installation / "chitin.key") != census["key_sha256"]:
        raise ValueError(f"{game} KEY differs from the resource census")
    for table in census["talk_tables"]:
        if sha256(installation / table["file"]) != table["sha256"]:
            raise ValueError(f"{game} talk table differs from the resource census")
    for resource in Chitin(installation / "chitin.key"):
        append(resource)
    capsules = {r["container"] for r in resources if r["storage"] == "capsule"}
    for relative in sorted(capsules):
        for resource in LazyCapsule(installation / relative, create_nonexisting=False):
            append(resource)
    pinned = {item["file"]: item for item in census["containers"]}
    for relative in sorted(selected):
        path = installation / relative
        info = path.stat()
        if info.st_size != pinned[relative]["file_size"]:
            raise ValueError(f"Container size changed: {game}/{relative}")
        digest = hashlib.sha256(
            json.dumps(observed[relative], separators=(",", ":")).encode()
        ).hexdigest()
        if digest != pinned[relative]["resource_index_sha256"]:
            raise ValueError(f"Container index changed: {game}/{relative}")
    return snapshots


def scan_loose_dialogues(game, installation, inventory_id):
    files = file_snapshot(installation)
    for path in installation.iterdir():
        if path.is_file() and path.suffix.casefold() == ".dlg":
            files[path] = path.stat()
    rows, snapshots = [], {}
    for path, info in sorted(files.items()):
        if path.suffix.casefold() != ".dlg":
            continue
        relative = path.relative_to(installation).as_posix()
        snapshots[path] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        rows.append(
            {
                "game": game,
                "inventory_id": inventory_id,
                "storage": "loose",
                "container": relative,
                "source_entry": 0,
                "resref": path.stem,
                "resource_type": "dlg",
                "resource_type_id": 2029,
                "offset": 0,
                "size": info.st_size,
                "resource_sha256": sha256(path),
            }
        )
    return rows, snapshots


def inventory_dialogues(root, installations, output):
    resources_path = root / "catalog/games/resources.parquet"
    census_path = root / "catalog/games/resource-census.json"
    manifest = json.loads((root / "manifest.json").read_text())
    pins = {item["path"]: item["sha256"] for item in manifest["input_files"]}
    for path in [resources_path, census_path]:
        if sha256(path) != pins[path.relative_to(root).as_posix()]:
            raise ValueError("Resource census differs from manifest")
    resources = pq.read_table(
        resources_path, filters=[("resource_type", "=", "dlg")]
    ).to_pylist()
    census = json.loads(census_path.read_text())
    source_games = {item["game"]: item for item in census["installations"]}
    games = dict(installations)
    if (
        len(games) != len(installations)
        or not games
        or set(games) - source_games.keys()
    ):
        raise ValueError("Supply unique game identifiers from the resource census")
    output.mkdir(parents=True, exist_ok=True)
    paths = {name: output / (name + ".parquet") for name in SCHEMAS}
    writers = {}
    buffers = {name: [] for name in SCHEMAS}
    for name, schema in SCHEMAS.items():
        temporary = paths[name].with_suffix(".parquet.tmp")
        statistics = [field for field in schema.names if field != "fields_json"]
        writers[name] = pq.ParquetWriter(
            temporary, schema, compression="zstd", write_statistics=statistics
        )
    totals, game_counts = Counter(), {}
    loose_resources = []
    loose_counts = {}
    try:
        for game, location in installations:
            installation = Path(location).resolve(strict=True)
            selected = sorted(
                (r for r in resources if r["game"] == game),
                key=lambda r: (r["container"], r["source_entry"]),
            )
            snapshots = verify_source_indices(
                game, installation, selected, source_games[game]
            )
            loose, loose_snapshots = scan_loose_dialogues(
                game, installation, source_games[game]["inventory_id"]
            )
            loose_resources.extend(loose)
            loose_counts[game] = len(loose)
            snapshots.update(loose_snapshots)
            selected = sorted(
                selected + loose, key=lambda r: (r["container"], r["source_entry"])
            )
            counts = Counter()
            for resource in selected:
                path = installation / resource["container"]
                with path.open("rb") as stream:
                    stream.seek(resource["offset"])
                    body = stream.read(resource["size"])
                if len(body) != resource["size"]:
                    raise ValueError("Truncated indexed dialogue resource")
                summary, nodes, edges = dialogue_records(resource, body)
                if (
                    resource["storage"] == "loose"
                    and summary["resource_sha256"] != resource["resource_sha256"]
                ):
                    raise ValueError("Loose dialogue changed after its source snapshot")
                for name, records in [
                    ("dialogues", [summary]),
                    ("dialogue-nodes", nodes),
                    ("dialogue-edges", edges),
                ]:
                    buffers[name].extend(records)
                    if len(buffers[name]) >= 256:
                        writers[name].write_table(
                            pa.Table.from_pylist(buffers[name], schema=SCHEMAS[name])
                        )
                        buffers[name].clear()
                    counts[name] += len(records)
                counts["invalid_edges"] += summary["invalid_edges"]
                counts["unreachable_nodes"] += summary["unreachable_nodes"]
            for path, before in snapshots.items():
                info = path.stat()
                if before != (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns):
                    raise ValueError(
                        "Source container changed during dialogue extraction"
                    )
            current_loose, current_snapshots = scan_loose_dialogues(
                game, installation, source_games[game]["inventory_id"]
            )
            if current_loose != loose or current_snapshots != loose_snapshots:
                raise ValueError("Loose dialogue population changed during extraction")
            game_counts[game] = dict(counts)
            totals.update(counts)
            print(game, dict(counts), flush=True)
        for name, records in buffers.items():
            if records:
                writers[name].write_table(
                    pa.Table.from_pylist(records, schema=SCHEMAS[name])
                )
    finally:
        for writer in writers.values():
            writer.close()
    for name, path in paths.items():
        path.with_suffix(".parquet.tmp").replace(path)
    loose_path = output / "loose-dialogue-resources.parquet"
    loose_temporary = loose_path.with_suffix(".parquet.tmp")
    pq.write_table(
        pa.Table.from_pylist(loose_resources, schema=LOOSE_SCHEMA),
        loose_temporary,
        compression="zstd",
    )
    loose_temporary.replace(loose_path)
    readers = {}
    for name, module in sorted(sys.modules.copy().items()):
        source = getattr(module, "__file__", None)
        if (
            name.startswith(("pykotor.", "utility."))
            and source
            and Path(source).is_file()
        ):
            readers[name] = sha256(Path(source))
    receipt = {
        "scope": "Every indexed DLG resource and observed loose DLG file in the declared installation asset directories and installation root. Static graph indices, typed functional metadata and hashes for withheld strings and binary fields. Source occurrences and duplicate physical fields are retained.",
        "limitations": "Script identifiers and numeric parameters are retained. String parameters have hashes. Scripts and conditions are not executed. Reachability ignores conditions and game state. Override and module precedence, runtime behavior, narrative text, other builds and languages remain unresolved.",
        "resource_index_sha256": sha256(resources_path),
        "resource_census_sha256": sha256(census_path),
        "producer_sha256": sha256(Path(__file__)),
        "reader_module_sha256": readers,
        "source_inventory_ids": {
            game: source_games[game]["inventory_id"] for game in games
        },
        "independent_validation": "Each DLG checked against direct binary GFF struct/field signatures, graph-list cardinalities and ordered link indices, independently of the PyKotor object reader.",
        "counts": dict(totals),
        "games": game_counts,
        "source_containers_stable": True,
        "loose_resources": {
            "file": loose_path.name,
            "rows": len(loose_resources),
            "sha256": sha256(loose_path),
            "games": loose_counts,
            "scope": "Standalone .dlg files under the inventoried asset directories and installation root. Inventory IDs anchor the matching packed-resource, KEY and talk-table context. Loose file bytes have their own hashes. Population and file metadata are checked before and after extraction.",
        },
        "embedded": False,
        "outputs": {
            name: {"file": path.name, "rows": totals[name], "sha256": sha256(path)}
            for name, path in paths.items()
        },
    }
    (output / "dialogue-census.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Staged observed dialogue graphs", dict(totals), flush=True)


def metadata_statistics(value):
    """Check withheld-value shapes and count represented physical fields."""
    if set(value) != {"struct_id", "fields"}:
        raise ValueError("Unexpected dialogue struct metadata")
    structs, fields = 1, len(value["fields"])
    for field in value["fields"]:
        if set(field) != {"label", "type", "value"}:
            raise ValueError("Unexpected dialogue field metadata")
        kind, data = field["type"], field["value"]
        if kind == "String":
            if (
                set(data) != {"withheld_text", "characters", "decoded_utf8_sha256"}
                or data["withheld_text"] is not True
            ):
                raise ValueError("Unscreened string in dialogue metadata")
        elif kind == "LocalizedString":
            if set(data) != {"stringref", "substrings"}:
                raise ValueError("Unexpected localized-string metadata")
            for item in data["substrings"]:
                if set(item) != {
                    "language",
                    "gender",
                    "characters",
                    "decoded_utf8_sha256",
                }:
                    raise ValueError("Unscreened localized prose in dialogue metadata")
        elif kind == "Struct":
            child_structs, child_fields = metadata_statistics(data)
            structs += child_structs
            fields += child_fields
        elif kind == "List":
            if isinstance(data, dict):
                if (
                    set(data) != {"external_graph_list", "items"}
                    or data["external_graph_list"] != field["label"]
                ):
                    raise ValueError("Unexpected external graph-list reference")
            else:
                for item in data:
                    child_structs, child_fields = metadata_statistics(item)
                    structs += child_structs
                    fields += child_fields
    return structs, fields


def verify_dialogue_files(directory, resources_path, census_path):
    receipt = json.loads((directory / "dialogue-census.json").read_text())
    if receipt["resource_index_sha256"] != sha256(resources_path) or receipt[
        "resource_census_sha256"
    ] != sha256(census_path):
        raise ValueError("Dialogue census has stale resource inputs")
    source_games = {
        item["game"]: item
        for item in json.loads(census_path.read_text())["installations"]
    }
    for game, inventory_id in receipt["source_inventory_ids"].items():
        if source_games[game]["inventory_id"] != inventory_id:
            raise ValueError("Dialogue census has an unknown source inventory")
    tables = {}
    for name, schema in SCHEMAS.items():
        path = directory / (name + ".parquet")
        pin = receipt["outputs"][name]
        table = pq.ParquetFile(path)
        if (
            table.schema_arrow != schema
            or table.metadata.num_rows != pin["rows"]
            or sha256(path) != pin["sha256"]
        ):
            raise ValueError(f"Dialogue table differs from its receipt: {name}")
        tables[name] = table

    resources = pq.read_table(
        resources_path, filters=[("resource_type", "=", "dlg")]
    ).to_pylist()
    loose_pin = receipt.get("loose_resources")
    if loose_pin:
        loose_path = directory / "loose-dialogue-resources.parquet"
        loose_table = pq.read_table(loose_path)
        if (
            loose_pin["file"] != loose_path.name
            or loose_table.schema != LOOSE_SCHEMA
            or loose_table.num_rows != loose_pin["rows"]
            or sha256(loose_path) != loose_pin["sha256"]
        ):
            raise ValueError("Loose dialogue index differs from receipt")
        loose = loose_table.to_pylist()
        actual_counts = {game: 0 for game in receipt["source_inventory_ids"]}
        for resource in loose:
            path = Path(resource["container"])
            if resource["game"] not in actual_counts or resource[
                "inventory_id"
            ] != receipt["source_inventory_ids"].get(resource["game"]):
                raise ValueError("Unknown loose dialogue source inventory")
            if (
                path.is_absolute()
                or ".." in path.parts
                or path.suffix.casefold() != ".dlg"
                or resource["resref"] != path.stem
            ):
                raise ValueError("Invalid loose dialogue path")
            if (
                resource["storage"] != "loose"
                or resource["offset"] != 0
                or resource["source_entry"] != 0
                or resource["resource_type"] != "dlg"
                or resource["resource_type_id"] != 2029
            ):
                raise ValueError("Invalid loose dialogue resource identity")
            actual_counts[resource["game"]] += 1
        if actual_counts != loose_pin["games"]:
            raise ValueError("Loose dialogue game counts differ")
        resources.extend(loose)
    expected = {}
    for resource in resources:
        if resource["game"] in receipt["source_inventory_ids"]:
            identity = (
                resource["inventory_id"]
                + "/"
                + resource["container"]
                + "#"
                + str(resource["source_entry"])
            )
            if identity in expected:
                raise ValueError("Duplicate dialogue resource identity")
            expected[identity] = resource
    summaries = {
        row["dialogue_id"]: row for row in tables["dialogues"].read().to_pylist()
    }
    if (
        len(summaries) != tables["dialogues"].metadata.num_rows
        or summaries.keys() != expected.keys()
    ):
        raise ValueError("Dialogue census omits or duplicates indexed resources")
    statistics = defaultdict(Counter)
    external_lists = {}
    actual_nodes = {}
    edges = defaultdict(list)
    physical_counts = defaultdict(Counter)

    def inspect(identity, metadata, kind, index):
        structs, fields = metadata_statistics(metadata)
        physical_counts[identity].update(structs=structs, fields=fields)
        for field in metadata["fields"]:
            data = field["value"]
            if field["type"] == "List" and isinstance(data, dict):
                external_lists[(identity, kind, index, field["label"])] = data["items"]

    for identity, row in summaries.items():
        source = expected[identity]
        if any(
            row[key] != source[key]
            for key in [
                "game",
                "inventory_id",
                "container",
                "source_entry",
                "resref",
                "offset",
                "size",
            ]
        ):
            raise ValueError("Dialogue identity differs from resource index")
        if (
            "resource_sha256" in source
            and row["resource_sha256"] != source["resource_sha256"]
        ):
            raise ValueError("Loose dialogue payload hash differs from source snapshot")
        inspect(identity, json.loads(row["fields_json"]), "root", -1)
    for batch in tables["dialogue-nodes"].iter_batches(batch_size=128):
        for row in batch.to_pylist():
            identity = row["dialogue_id"]
            key = (identity, row["node_kind"], row["node_index"])
            if (
                identity not in summaries
                or key in actual_nodes
                or row["node_kind"] not in {"entry", "reply"}
            ):
                raise ValueError("Unknown or duplicate dialogue node")
            if (
                not 0
                <= row["node_index"]
                < summaries[identity][row["node_kind"] + "_nodes"]
            ):
                raise ValueError("Node index exceeds source list")
            actual_nodes[key] = row["potentially_reachable"]
            statistics[identity][row["node_kind"]] += 1
            statistics[identity]["reachable"] += row["potentially_reachable"]
            metadata = json.loads(row["fields_json"])
            texts = [
                field["value"]
                for field in metadata["fields"]
                if field["label"] == "Text" and field["type"] == "LocalizedString"
            ]
            text = texts[0] if len(texts) == 1 else None
            if row["text_stringref"] != (
                text["stringref"] if text is not None else None
            ) or row["inline_localizations"] != (
                len(text["substrings"]) if text is not None else None
            ):
                raise ValueError("Node text references differ from typed metadata")
            inspect(identity, metadata, row["node_kind"], row["node_index"])
    seen_edges = set()
    source_edges = defaultdict(list)
    for batch in tables["dialogue-edges"].iter_batches(batch_size=128):
        for row in batch.to_pylist():
            identity = row["dialogue_id"]
            key = (identity, row["source_kind"], row["source_index"], row["edge_index"])
            if identity not in summaries or key in seen_edges:
                raise ValueError("Unknown or duplicate dialogue edge")
            seen_edges.add(key)
            source_key = key[:3]
            if row["source_kind"] == "start":
                if row["source_index"] != -1 or row["target_kind"] != "entry":
                    raise ValueError("Invalid starting-edge identity")
            elif (
                source_key not in actual_nodes
                or row["target_kind"]
                != {"entry": "reply", "reply": "entry"}[row["source_kind"]]
            ):
                raise ValueError("Invalid dialogue-edge source")
            valid = (identity, row["target_kind"], row["target_index"]) in actual_nodes
            if valid != row["target_valid"]:
                raise ValueError("Dialogue-edge target validity differs")
            metadata = json.loads(row["fields_json"])
            indices = [
                field["value"]
                for field in metadata["fields"]
                if field["label"] == "Index"
            ]
            index = (
                indices[0]
                if len(indices) == 1 and isinstance(indices[0], int)
                else None
            )
            if index != row["target_index"]:
                raise ValueError("Edge target differs from typed metadata")
            inspect(identity, metadata, "edge", len(seen_edges))
            source_edges[source_key].append(row["edge_index"])
            statistics[identity]["edges"] += 1
            statistics[identity]["starting_edges"] += row["source_kind"] == "start"
            statistics[identity]["invalid_edges"] += not valid
            edges[identity].append(
                {
                    key: row[key]
                    for key in [
                        "source_kind",
                        "source_index",
                        "target_kind",
                        "target_index",
                        "target_valid",
                    ]
                }
            )
    for key, indices in source_edges.items():
        if sorted(indices) != list(range(len(indices))):
            raise ValueError("Noncontiguous dialogue link positions")
    by_game = defaultdict(Counter)
    for identity, row in summaries.items():
        for kind in ["entry", "reply"]:
            if statistics[identity][kind] != row[kind + "_nodes"]:
                raise ValueError("Dialogue node cardinality differs")
        for key in ["edges", "starting_edges", "invalid_edges"]:
            if statistics[identity][key] != row[key]:
                raise ValueError("Dialogue edge cardinality differs")
        for field, expected_count in [
            ("EntryList", row["entry_nodes"]),
            ("ReplyList", row["reply_nodes"]),
            ("StartingList", row["starting_edges"]),
        ]:
            if external_lists.get((identity, "root", -1, field), 0) != expected_count:
                raise ValueError("Root graph-list cardinality differs")
        for kind, count, label in [
            ("entry", row["entry_nodes"], "RepliesList"),
            ("reply", row["reply_nodes"], "EntriesList"),
        ]:
            for index in range(count):
                if external_lists.get((identity, kind, index, label), 0) != len(
                    source_edges[(identity, kind, index)]
                ):
                    raise ValueError("Node graph-list cardinality differs")
        reachable = reachable_nodes(edges[identity])
        if (
            row["entry_nodes"] + row["reply_nodes"] - len(reachable)
            != row["unreachable_nodes"]
        ):
            raise ValueError("Static reachability total differs")
        for kind, index in reachable:
            if actual_nodes[(identity, kind, index)] is not True:
                raise ValueError("Static reachability flag differs")
        if statistics[identity]["reachable"] != len(reachable):
            raise ValueError("Unexpected static reachability flags")
        if (
            physical_counts[identity]["structs"] != row["physical_struct_occurrences"]
            or physical_counts[identity]["fields"] != row["physical_field_occurrences"]
        ):
            raise ValueError(
                "Represented physical field counts differ from binary audit"
            )
        by_game[row["game"]].update(
            {
                "dialogues": 1,
                "dialogue-nodes": row["entry_nodes"] + row["reply_nodes"],
                "dialogue-edges": row["edges"],
                "invalid_edges": row["invalid_edges"],
                "unreachable_nodes": row["unreachable_nodes"],
            }
        )
    if {game: dict(counts) for game, counts in by_game.items()} != receipt["games"]:
        raise ValueError("Per-game dialogue census counts differ")
    total = Counter()
    for counts in by_game.values():
        total.update(counts)
    if dict(total) != receipt["counts"] or receipt["embedded"] is not False:
        raise ValueError("Dialogue census totals or processing status differ")


def verify_dialogues(root):
    verify_dialogue_files(
        root / "catalog/games",
        root / "catalog/games/resources.parquet",
        root / "catalog/games/resource-census.json",
    )
