"""Collect publisher-provided edition identifiers, not publisher prose or book text."""

import datetime
import hashlib
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

source = json.loads(Path("catalog/sources/source-inventory.json").read_text())
selected = [
    x
    for x in source
    if x["id"].startswith("old-republic-book-") and "penguinrandomhouse.com" in x["url"]
]
previous = (
    json.loads(Path("catalog/works/publisher-edition-inventory.json").read_text())
    if Path("catalog/works/publisher-edition-inventory.json").exists()
    else {"works": []}
)
previous_by_id = {x["source_inventory_id"]: x for x in previous["works"]}
records = []
for entry in selected:
    response = requests.get(
        entry["url"],
        timeout=45,
        headers={"User-Agent": "HoloVec/0.1 (https://github.com/kolto-labs/holovec)"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    entities = []
    for node in soup.find_all("script", type="application/ld+json"):
        if not node.string:
            continue
        doc = json.loads(node.string)
        if (
            isinstance(doc, dict)
            and isinstance(doc.get("mainEntity"), dict)
            and doc["mainEntity"].get("@type") == "Book"
        ):
            entities.append(doc["mainEntity"])
    if len(entities) != 1:
        raise ValueError("Expected one publisher book entity: " + entry["id"])
    book = entities[0]
    editions = []
    for item in book.get("workExample", []):
        isbn = str(item.get("isbn", ""))
        if (
            len(isbn) != 13
            or not isbn.isdigit()
            or sum(
                int(digit) * (1 if index % 2 == 0 else 3)
                for index, digit in enumerate(isbn)
            )
            % 10
        ):
            raise ValueError("Invalid edition ISBN: " + entry["id"])
        editions.append(
            {
                "isbn13": isbn,
                "format": item.get("bookFormat", "").removeprefix(
                    "https://schema.org/"
                ),
                "publication_date": item.get("datePublished"),
                "publisher_edition_url": item.get("sameAs"),
            }
        )
    if not editions:
        raise ValueError("No editions: " + entry["id"])
    html_digest = hashlib.sha256(response.content).hexdigest()
    cache = Path("staging/sources/publisher-editions")
    cache.mkdir(parents=True, exist_ok=True)
    (cache / (entry["id"] + "-" + html_digest + ".html")).write_bytes(response.content)
    records.append(
        {
            "source_inventory_id": entry["id"],
            "publisher_work_title": book.get("name"),
            "publisher_author": book.get("author"),
            "publisher_language": book.get("inLanguage"),
            "source_url": entry["url"],
            "resolved_url": response.url,
            "source_html_sha256": html_digest,
            "editions": editions,
            "work_kind": entry.get("work_kind"),
            "relevance_scope": entry.get("relevance_scope"),
            "primary_content": "not acquired",
            "permission_to_redistribute_primary": "not established",
        }
    )
for record in records:
    old = previous_by_id.get(record["source_inventory_id"], {})
    for key in (
        "secondary_plot",
        "chronology_note",
        "chronology_source",
        "permission_for_hosted_processing",
    ):
        if key in old:
            record[key] = old[key]
output = {
    "description": "Publisher-listed edition identifiers for selected existing Old Republic and adjacent work leads, including one reference work. Bibliographic metadata only; current publisher selection is not a complete edition or work census, original publication chronology, content license, or narrative representation.",
    "retrieved_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "method": "Publisher JSON-LD mainEntity Book workExample; each page SHA-256 pins retrieved HTML, which is not republished.",
    "works": records,
}
destination = Path("catalog/works/publisher-edition-inventory.json")
temporary = destination.with_suffix(".json.tmp")
temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
temporary.replace(destination)
print("Works", len(records), "editions", sum(len(x["editions"]) for x in records))
