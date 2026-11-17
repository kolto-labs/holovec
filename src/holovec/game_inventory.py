"""Inventory local game resource headers without exporting resource payloads."""

import collections
import hashlib
import json
import os
import sys
from importlib import import_module
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ASSET_DIRECTORIES = {
    "data",
    "modules",
    "rims",
    "lips",
    "texturepacks",
    "override",
    "streammusic",
    "streamsounds",
    "streamvoice",
    "streamwaves",
    "movies",
    "ambient",
}
CAPSULE_SUFFIXES = {".rim", ".erf", ".mod"}
INDEX_FIELDS = (
    "source_entry",
    "resref",
    "resource_type",
    "resource_type_id",
    "offset",
    "size",
)
ROOT_FILES = {"chitin.key", "dialog.tlk", "dialogf.tlk", "swkotor.exe", "swkotor2.exe"}
SCHEMA = pa.schema(
    [
        ("game", pa.string()),
        ("inventory_id", pa.string()),
        ("storage", pa.string()),
        ("container", pa.string()),
        ("source_entry", pa.int64()),
        ("resref", pa.string()),
        ("resource_type", pa.string()),
        ("resource_type_id", pa.int64()),
        ("offset", pa.int64()),
        ("size", pa.int64()),
    ]
)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fail_walk(error):
    raise error


def file_snapshot(root):
    """Follow asset-directory links while preventing traversal cycles."""
    files = {}
    for child in root.iterdir():
        if child.is_file() and child.name.casefold() in ROOT_FILES:
            files[child] = child.stat()
        if not child.is_dir() or child.name.casefold() not in ASSET_DIRECTORIES:
            continue
        visited = set()
        for directory, subdirs, names in os.walk(
            child, followlinks=True, onerror=fail_walk
        ):
            directory = Path(directory)
            identity = directory.stat()
            key = (identity.st_dev, identity.st_ino)
            if key in visited:
                subdirs[:] = []
                continue
            visited.add(key)
            for name in names:
                path = directory / name
                if path.is_file():
                    files[path] = path.stat()
    return files


def fingerprints(files):
    return {
        str(path): (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        for path, info in files.items()
    }


def inventory_installation(game, root):
    from pykotor.extract.capsule import LazyCapsule
    from pykotor.extract.chitin import Chitin
    from pykotor.extract.talktable import TalkTable

    if game not in {"k1", "k2"}:
        raise ValueError("Supported game identifiers are k1 and k2")
    root = root.resolve(strict=True)
    before = file_snapshot(root)
    roots = {path.name.casefold(): path for path in before if path.parent == root}
    if "chitin.key" not in roots or "dialog.tlk" not in roots:
        raise ValueError(f"{game} requires chitin.key and dialog.tlk")
    rows = []
    container_rows = collections.defaultdict(list)

    def append_resource(resource, storage):
        path = Path(resource.filepath())
        relative = path.relative_to(root).as_posix()
        info = path.stat()
        offset, size = resource.offset(), resource.size()
        if offset < 0 or size < 0 or offset + size > info.st_size:
            raise ValueError(f"Resource bounds exceed {relative}")
        row = {
            "game": game,
            "inventory_id": None,
            "storage": storage,
            "container": relative,
            "source_entry": len(container_rows[relative]),
            "resref": resource.resname(),
            "resource_type": resource.restype().extension,
            "resource_type_id": resource.restype().type_id,
            "offset": offset,
            "size": size,
        }
        rows.append(row)
        container_rows[relative].append(row)

    base_counts = collections.Counter()
    chitin = Chitin(roots["chitin.key"])
    for resource in chitin:
        append_resource(resource, "bif")
        base_counts[resource.restype().extension] += 1
    capsules = [
        path
        for path in before
        if path.suffix.casefold() in CAPSULE_SUFFIXES
        and path.relative_to(root).parts[0].casefold() != "override"
    ]
    for path in sorted(capsules):
        relative = path.relative_to(root).as_posix()
        container_rows.setdefault(relative, [])
        for resource in LazyCapsule(path, create_nonexisting=False):
            append_resource(resource, "capsule")

    talk_tables = []
    for name in ["dialog.tlk", "dialogf.tlk"]:
        if name in roots:
            table = TalkTable(roots[name])
            talk_tables.append(
                {
                    "file": name,
                    "sha256": sha256(roots[name]),
                    "entries": table.size(),
                    "language": table.language().name,
                }
            )
    containers = []
    for name, entries in sorted(container_rows.items()):
        values = [[entry[field] for field in INDEX_FIELDS] for entry in entries]
        encoded = json.dumps(values, separators=(",", ":")).encode()
        containers.append(
            {
                "file": name,
                "entries": len(entries),
                "file_size": (root / name).stat().st_size,
                "resource_index_sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
    identity = {
        "game": game,
        "key_sha256": sha256(roots["chitin.key"]),
        "talk_tables": talk_tables,
        "containers": containers,
        "executables": [
            {"file": name, "sha256": sha256(path), "size": path.stat().st_size}
            for name, path in sorted(roots.items())
            if name.endswith(".exe")
        ],
    }
    inventory_id = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()
    ).hexdigest()
    for row in rows:
        row["inventory_id"] = inventory_id
    asset_counts = collections.defaultdict(collections.Counter)
    for path, info in before.items():
        group = path.relative_to(root).parts[0]
        asset_counts[group]["files"] += 1
        asset_counts[group]["bytes"] += info.st_size
    after = file_snapshot(root)
    if fingerprints(before) != fingerprints(after):
        raise ValueError(f"{game} asset files changed during inventory")
    summary = {
        **identity,
        "inventory_id": inventory_id,
        "source_kind": "Observed local harness asset tree; distribution, build and modification provenance unverified",
        "base_resources": len(chitin),
        "base_types": dict(sorted(base_counts.items())),
        "indexed_resources": len(rows),
        "indexed_containers": len(containers),
        "indexed_types": dict(
            sorted(collections.Counter(row["resource_type"] for row in rows).items())
        ),
        "observed_asset_files": dict(sorted(asset_counts.items())),
        "scope": "KEY-referenced BIF resource tables and discovered RIM, ERF and MOD resource tables. Loose assets and override files are counted only. Resource payloads, dialogue text, branch state and original-build fidelity are unverified.",
        "metadata_stable_during_read": True,
    }
    return rows, summary


def inventory_games(installations, output):
    try:
        import_module("pykotor.extract.chitin")
    except ImportError as error:
        raise SystemExit(
            "Game inventory requires PyKotor and its Utility dependency on the Python path."
        ) from error
    all_rows, summaries = [], []
    for game, path in installations:
        rows, summary = inventory_installation(game, Path(path))
        all_rows.extend(rows)
        summaries.append(summary)
        print(
            f'{game}: {len(rows):,} resource entries in {summary["indexed_containers"]} containers'
        )
    readers = {}
    for name, module in sorted(sys.modules.copy().items()):
        source = getattr(module, "__file__", None)
        if (
            name.startswith(("pykotor.", "utility."))
            and source
            and Path(source).is_file()
        ):
            readers[name] = sha256(Path(source))
    output.mkdir(parents=True, exist_ok=True)
    target = output / "resources.parquet"
    temporary = output / "resources.parquet.tmp"
    pq.write_table(
        pa.Table.from_pylist(all_rows, schema=SCHEMA), temporary, compression="zstd"
    )
    digest = sha256(temporary)
    temporary.replace(target)
    report = {
        "schema_version": 1,
        "kind": "Observed game-resource metadata census",
        "license": "CC0-1.0 for HoloVec-authored factual index metadata; underlying game resource rights remain separate",
        "resource_payloads_included": False,
        "inference_run": False,
        "resources": {
            "path": "catalog/games/resources.parquet",
            "rows": len(all_rows),
            "sha256": digest,
        },
        "reader_module_sha256": readers,
        "inventory_tool_sha256": sha256(Path(__file__)),
        "container_index_digest_fields": list(INDEX_FIELDS),
        "installations": summaries,
        "limitations": [
            "Observed harness trees have unverified modification and build provenance.",
            "Container indices identify candidate resources; narrative completeness, state-dependent traversal and payload content are unverified.",
            "Loose and override assets have aggregate counts only. Other builds, platforms, patches and languages require separate inventories.",
        ],
    }
    receipt = output / "resource-census.json.tmp"
    receipt.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    receipt.replace(output / "resource-census.json")
    print(f"Staged {len(all_rows):,} resource metadata records in {output}")


def verify_census(root):
    report = json.loads((root / "catalog/games/resource-census.json").read_text())
    resource_path = Path(report["resources"]["path"])
    if resource_path.is_absolute() or ".." in resource_path.parts:
        raise ValueError("Invalid resource catalog path")
    path = root / resource_path
    if sha256(path) != report["resources"]["sha256"]:
        raise ValueError("Resource catalog hash mismatch")
    installations = {item["inventory_id"]: item for item in report["installations"]}
    if len(installations) != len(report["installations"]):
        raise ValueError("Duplicate game inventory IDs")
    expected = {}
    for inventory_id, item in installations.items():
        for container in item["containers"]:
            expected[(inventory_id, container["file"])] = container
    indices = {key: [] for key in expected}
    types = collections.defaultdict(collections.Counter)
    count = 0
    for batch in pq.ParquetFile(path).iter_batches():
        for row in batch.to_pylist():
            inventory_id = row["inventory_id"]
            key = (inventory_id, row["container"])
            if (
                key not in expected
                or row["game"] != installations[inventory_id]["game"]
            ):
                raise ValueError("Unregistered resource container or game")
            relative = Path(row["container"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Invalid resource container path")
            if row["source_entry"] != len(indices[key]):
                raise ValueError("Resource entry sequence mismatch")
            if (
                row["offset"] < 0
                or row["size"] < 0
                or row["offset"] + row["size"] > expected[key]["file_size"]
            ):
                raise ValueError("Resource catalog entry exceeds container size")
            indices[key].append(
                [row[field] for field in report["container_index_digest_fields"]]
            )
            types[inventory_id][row["resource_type"]] += 1
            count += 1
    for key, entries in indices.items():
        container = expected[key]
        digest = hashlib.sha256(
            json.dumps(entries, separators=(",", ":")).encode()
        ).hexdigest()
        if (
            len(entries) != container["entries"]
            or digest != container["resource_index_sha256"]
        ):
            raise ValueError("Resource container index mismatch")
    for inventory_id, item in installations.items():
        if (
            dict(types[inventory_id]) != item["indexed_types"]
            or sum(types[inventory_id].values()) != item["indexed_resources"]
        ):
            raise ValueError("Game resource count mismatch")
    if count != report["resources"]["rows"]:
        raise ValueError("Resource catalog row count mismatch")
    return count
