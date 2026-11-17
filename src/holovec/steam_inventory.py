"""Compare local game files with a cached Steam depot manifest."""

import collections
import hashlib
import json
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path, PurePosixPath

import pyarrow as pa
import pyarrow.parquet as pq

from .game_inventory import sha256

SCHEMA = pa.schema(
    [
        ("installation", pa.string()),
        ("app_id", pa.int64()),
        ("depot_id", pa.int64()),
        ("manifest_id", pa.string()),
        ("path", pa.string()),
        ("reference_kind", pa.string()),
        ("expected_size", pa.int64()),
        ("expected_sha1", pa.string()),
        ("actual_size", pa.int64()),
        ("actual_sha1", pa.string()),
        ("status", pa.string()),
    ]
)


def fingerprint(path):
    if path is None:
        return None
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


class CaseLookup:
    """Resolve Windows depot paths against case-sensitive local filesystems."""

    def __init__(self, root):
        self.root = root
        self.directories = {}

    def resolve(self, relative):
        current = self.root
        for part in PurePosixPath(relative).parts:
            exact = current / part
            if exact.exists():
                current = exact
                continue
            if current not in self.directories:
                entries = collections.defaultdict(list)
                if current.is_dir():
                    for child in current.iterdir():
                        entries[child.name.casefold()].append(child)
                self.directories[current] = entries
            candidates = self.directories[current].get(part.casefold(), [])
            if len(candidates) > 1:
                raise ValueError(f"Ambiguous case-insensitive depot path: {relative}")
            if not candidates:
                return None
            current = candidates[0]
        return current


def compare_steam(appmanifest, depot_manifest, installations, output):
    try:
        vdf = import_module("vdf")
        parser = import_module("steam.core.manifest")
    except ImportError as error:
        raise SystemExit(
            "Steam comparison requires ValvePython steam and vdf in the Python environment."
        ) from error
    raw = depot_manifest.read_bytes()
    depot = parser.DepotManifest(raw)
    app = vdf.loads(appmanifest.read_text())["AppState"]
    installed = app["InstalledDepots"].get(str(depot.depot_id))
    if installed is None or installed["manifest"] != str(depot.gid):
        raise ValueError(
            "Cached depot manifest differs from the client installation declaration"
        )
    if depot.filenames_encrypted:
        raise ValueError("The cached manifest has encrypted filenames")
    labels = [label for label, _ in installations]
    if len(labels) != len(set(labels)):
        raise ValueError("Duplicate installation labels")
    files = list(depot.iter_files())
    rows, summaries = [], []
    for label, supplied_root in installations:
        root = Path(supplied_root).resolve(strict=True)
        lookup = CaseLookup(root)
        snapshots = []
        start = len(rows)
        for ordinal, file in enumerate(files):
            relative = file.filename_raw.replace("\\", "/")
            parsed = PurePosixPath(relative)
            if parsed.is_absolute() or ".." in parsed.parts:
                raise ValueError("Unsafe path in depot manifest")
            path = lookup.resolve(relative)
            before = fingerprint(path)
            actual_hash = None
            kind = "directory" if file.is_directory else "file"
            if file.is_symlink:
                kind = "symlink"
                status = "symlink_reference_unverified"
            elif path is None:
                status = "missing"
            elif file.is_directory:
                status = "directory_present" if path.is_dir() else "wrong_type"
            elif not path.is_file():
                status = "wrong_type"
            else:
                with path.open("rb") as stream:
                    actual_hash = hashlib.file_digest(stream, "sha1").hexdigest()
                if before != fingerprint(path):
                    status = "changed_during_read"
                elif not file.file_mapping.sha_content:
                    status = "reference_hash_absent"
                elif (
                    actual_hash != file.file_mapping.sha_content.hex()
                    or before[2] != file.size
                ):
                    status = "different"
                else:
                    status = "matches_reference"
            rows.append(
                {
                    "installation": label,
                    "app_id": int(app["appid"]),
                    "depot_id": depot.depot_id,
                    "manifest_id": str(depot.gid),
                    "path": relative,
                    "reference_kind": kind,
                    "expected_size": file.size,
                    "expected_sha1": file.file_mapping.sha_content.hex() or None,
                    "actual_size": before[2] if before is not None else None,
                    "actual_sha1": actual_hash,
                    "status": status,
                }
            )
            snapshots.append(before)
            if (ordinal + 1) % 1000 == 0:
                print(
                    f"{label}: checked {ordinal + 1:,}/{len(files):,} depot entries",
                    flush=True,
                )
        final_lookup = CaseLookup(root)
        for row, before in zip(rows[start:], snapshots, strict=True):
            if fingerprint(final_lookup.resolve(row["path"])) != before:
                row["status"] = "changed_after_read"
        counts = dict(
            sorted(collections.Counter(row["status"] for row in rows[start:]).items())
        )
        summaries.append(
            {"installation": label, "entries": len(files), "statuses": counts}
        )
        print(f"{label}: {json.dumps(counts)}", flush=True)
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / "distribution-files.parquet.tmp"
    pq.write_table(
        pa.Table.from_pylist(rows, schema=SCHEMA), temporary, compression="zstd"
    )
    digest = sha256(temporary)
    temporary.replace(output / "distribution-files.parquet")
    report = {
        "schema_version": 1,
        "kind": "Local file comparison with locally cached Steam depot metadata",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "license": "CC0-1.0 for HoloVec-authored factual observations; underlying game rights remain separate",
        "client_declaration": {
            "app_id": int(app["appid"]),
            "build_id": app.get("buildid"),
            "installed_depot_id": depot.depot_id,
            "installed_manifest_id": str(depot.gid),
            "declared_depot_bytes": int(installed["size"]),
        },
        "reference": {
            "depot_id": depot.depot_id,
            "manifest_id": str(depot.gid),
            "cached_manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "manifest_entries": len(files),
            "signature_cryptographically_verified": False,
        },
        "observations": summaries,
        "comparison_data": {
            "path": "catalog/games/distribution-files.parquet",
            "rows": len(rows),
            "sha256": digest,
        },
        "comparison_tool_sha256": sha256(Path(__file__)),
        "reader_module_sha256": {
            name: sha256(Path(module.__file__))
            for name, module in [("steam.core.manifest", parser), ("vdf", vdf)]
        },
        "limitations": [
            "The reference is a local cached manifest associated with a local Steam client declaration.",
            "The reader parses the manifest; its Steam signature has not been cryptographically verified.",
            "Comparisons cover listed depot paths. Additional local files, other depots, builds, platforms and languages require separate inventories.",
            "File hashes establish byte correspondence to this reference. Original game content rights and narrative completeness remain unresolved.",
        ],
    }
    receipt = output / "distribution-verification.json.tmp"
    receipt.write_text(json.dumps(report, indent=2) + "\n")
    receipt.replace(output / "distribution-verification.json")
    print(f"Staged {len(rows):,} depot-file observations in {output}")


def verify_comparison(root):
    report = json.loads(
        (root / "catalog/games/distribution-verification.json").read_text()
    )
    relative = Path(report["comparison_data"]["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Invalid distribution comparison path")
    path = root / relative
    if sha256(path) != report["comparison_data"]["sha256"]:
        raise ValueError("Distribution comparison hash mismatch")
    parquet = pq.ParquetFile(path)
    if parquet.schema_arrow != SCHEMA:
        raise ValueError("Unexpected distribution comparison schema")
    expected = {item["installation"]: item for item in report["observations"]}
    if len(expected) != len(report["observations"]):
        raise ValueError("Duplicate distribution observation labels")
    counts = collections.defaultdict(collections.Counter)
    reference_paths = {}
    observed = {}
    for batch in parquet.iter_batches():
        for row in batch.to_pylist():
            label = row["installation"]
            if label not in expected:
                raise ValueError("Unknown distribution observation label")
            relative = PurePosixPath(row["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Invalid depot entry path")
            if (
                row["app_id"] != report["client_declaration"]["app_id"]
                or row["depot_id"] != report["reference"]["depot_id"]
                or row["manifest_id"] != report["reference"]["manifest_id"]
            ):
                raise ValueError("Distribution reference identity mismatch")
            identity = (
                row["reference_kind"],
                row["expected_size"],
                row["expected_sha1"],
            )
            if (
                row["path"] in reference_paths
                and reference_paths[row["path"]] != identity
            ):
                raise ValueError("Conflicting depot entry reference")
            reference_paths[row["path"]] = identity
            key = (label, row["path"].casefold())
            if key in observed:
                raise ValueError("Duplicate case-insensitive depot path")
            observed[key] = row["status"]
            if row["status"] == "matches_reference" and (
                row["reference_kind"] != "file"
                or row["actual_size"] != row["expected_size"]
                or not row["actual_sha1"]
                or row["actual_sha1"] != row["expected_sha1"]
            ):
                raise ValueError("Invalid matching-file observation")
            counts[label][row["status"]] += 1
    for label, item in expected.items():
        if (
            dict(counts[label]) != item["statuses"]
            or sum(counts[label].values()) != report["reference"]["manifest_entries"]
            or sum(counts[label].values()) != item["entries"]
        ):
            raise ValueError("Distribution observation counts mismatch")
    total = sum(sum(group.values()) for group in counts.values())
    if (
        total != report["comparison_data"]["rows"]
        or len(reference_paths) != report["reference"]["manifest_entries"]
    ):
        raise ValueError("Distribution comparison row count mismatch")
    catalog = json.loads((root / "catalog/games/resource-census.json").read_text())
    inventories = {item["inventory_id"]: item for item in catalog["installations"]}
    sources = json.loads((root / "catalog/sources/source-inventory.json").read_text())
    for source in sources:
        link = source.get("distribution_comparison")
        if not link:
            continue
        inventory = inventories[link["resource_inventory_id"]]
        matched = [
            container
            for container in inventory["containers"]
            if observed.get((link["installation"], container["file"].casefold()))
            == "matches_reference"
        ]
        if (
            len(matched) != link["matching_indexed_containers"]
            or sum(container["entries"] for container in matched)
            != link["matching_indexed_resources"]
        ):
            raise ValueError("Resource-to-distribution comparison link mismatch")
    return total
