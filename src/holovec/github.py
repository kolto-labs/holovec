"""Stage reviewed GitHub documents using pinned commits and Git blob hashes."""

import base64
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote


def fetch_document(repository, path, expected_blob):
    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/git/blobs/{expected_blob}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    blob = json.loads(result.stdout)
    if blob.get("sha") != expected_blob or blob.get("encoding") != "base64":
        raise ValueError(f"Unexpected Git blob metadata for {repository}/{path}")
    body = base64.b64decode("".join(blob["content"].split()), validate=True)
    actual = hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
    if actual != expected_blob:
        raise ValueError(f"Source blob hash mismatch for {repository}/{path}")
    return body


def stage_documents(root, repository):
    recipes = json.loads((root / "catalog/github-document-recipes.json").read_text())
    recipe = recipes["repositories"][repository]
    commit = recipe["commit"]
    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/git/trees/{commit}?recursive=1"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    tree = json.loads(result.stdout)
    if tree.get("truncated"):
        raise ValueError("Repository tree is truncated")
    if recipe.get("tree_sha") and tree["sha"] != recipe["tree_sha"]:
        raise ValueError("Repository tree hash mismatch")
    blobs = {
        item["path"]: item["sha"] for item in tree["tree"] if item["type"] == "blob"
    }
    expected = {path: item["blob_sha"] for path, item in recipe["documents"].items()}
    excluded = recipe.get("excluded_documents", {})
    if set(expected) & set(excluded):
        raise ValueError("A document cannot be selected and excluded")
    for path, disposition in excluded.items():
        if not disposition.get("reason"):
            raise ValueError(f"Excluded document lacks a disposition: {path}")
        expected[path] = disposition["blob_sha"]
    expected[recipe["license_path"]] = recipe["license_blob"]
    for path, digest in expected.items():
        if blobs.get(path) != digest:
            raise ValueError(f"Pinned tree path mismatch for {repository}/{path}")
    if recipe.get("complete_prefixes"):
        scoped = {
            path
            for path in blobs
            if any(path.startswith(prefix) for prefix in recipe["complete_prefixes"])
        }
        scoped.update(recipe.get("additional_paths", []))
        if scoped != set(recipe["documents"]) | set(excluded):
            raise ValueError(
                "Recipe does not match the complete declared directory scope"
            )
    license_body = fetch_document(
        repository, recipe["license_path"], recipe["license_blob"]
    )
    documents = sorted(recipe["documents"].items())

    def fetch(item):
        path, document = item
        return fetch_document(repository, path, document["blob_sha"])

    with ThreadPoolExecutor(max_workers=4) as pool:
        bodies = list(pool.map(fetch, documents))
    rows = []
    for (path, document), body in zip(documents, bodies, strict=True):
        expected_blob = document["blob_sha"]
        text = body.decode(document["encoding"])
        url = f'https://github.com/{repository}/blob/{commit}/{quote(path, safe="/")}'
        rows.append(
            {
                "title": repository + " / " + path,
                "repository": repository,
                "commit": commit,
                "path": path,
                "blob_sha": expected_blob,
                "source_url": url,
                "text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "source_sha256": hashlib.sha256(body).hexdigest(),
                "source_encoding": document["encoding"],
                "alterations": "Decoded original source bytes using the declared source encoding; text and line endings otherwise retained.",
                "license_spdx": recipe["license"],
                "license_path": recipe["license_path"],
                "license_copy": recipe["license_copy"],
                "license_blob": recipe["license_blob"],
                "license_evidence": document.get(
                    "license_evidence", recipe["license_evidence"]
                ),
                "attribution": "Repository contributors; see pinned file history and retained credits",
                "evidence_class": document.get(
                    "evidence_class",
                    recipe.get("evidence_class", "technical_project_documentation"),
                ),
                "coverage": document.get("coverage", recipe["coverage"]),
                "embedded": False,
            }
        )
    staging = root / "staging/github-documents" / repository
    staging.mkdir(parents=True, exist_ok=True)
    license_path = staging / Path(recipe["license_copy"]).name
    license_path.write_bytes(license_body)
    output = staging / "documents.jsonl"
    temporary = output.with_suffix(".jsonl.tmp")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        )
    )
    temporary.replace(output)
    print(f"Staged {len(rows)} pinned documents in {output.relative_to(root)}")
