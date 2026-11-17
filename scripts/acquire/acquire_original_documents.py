"""Stage byte-pinned original documents from the reviewed source catalog."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import requests

root = Path(__file__).resolve().parents[2]
catalog = json.loads((root / "catalog/sources/original-documents.json").read_text())
output = root / "staging/original-documents"
output.mkdir(parents=True, exist_ok=True)

for document in catalog["documents"]:
    relative = Path(document["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe document path: {relative}")
    response = requests.get(document["download_url"], timeout=90)
    response.raise_for_status()
    payload = response.content
    digest = hashlib.sha256(payload).hexdigest()
    if len(payload) != document["size"] or digest != document["sha256"]:
        raise ValueError(f"Source version changed: {document['source_inventory_id']}")
    if not payload.startswith(b"%PDF-"):
        raise ValueError(f"Expected PDF: {document['source_inventory_id']}")
    target = output / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Staged {document['source_inventory_id']} ({digest})")
