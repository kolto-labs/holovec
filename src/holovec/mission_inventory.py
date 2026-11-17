"""Extract attributed factual mission metadata from a pinned workbook snapshot."""

import collections
import hashlib
import json
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .game_inventory import sha256

ENTRY_ROLES = {
    "live",
    "test_server",
    "conquest",
    "retired",
    "seasonal",
    "legacy_backup",
}


def label(value):
    return " ".join(str(value).split()).casefold()


def scalar(value):
    return None if value is None else str(value)


def verify_source_cells(source, rows):
    """Cross-check extracted facts against raw worksheet XML and shared strings."""
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    relationships = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    document_relationship = (
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    )
    expected = collections.defaultdict(dict)
    issues = {}
    checked = 0
    for row in rows:
        for issue in row["source_cell_issues"]:
            issues[(row["source_sheet"], issue["cell"])] = issue
        for field, address in row["source_cells"].items():
            expected[row["source_sheet"]][address] = row["mission_metadata"][field]
    with ZipFile(source) as archive:
        strings = [
            "".join(item.itertext())
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml"))
        ]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relations.findall(relationships + "Relationship")
        }
        for sheet in workbook.find(namespace + "sheets"):
            name = sheet.attrib["name"]
            if name not in expected:
                continue
            target = targets[sheet.attrib[document_relationship]]
            path = target.lstrip("/") if target.startswith("/") else "xl/" + target
            observed = set()
            xml = ET.fromstring(archive.read(path))
            for cell in xml.iter(namespace + "c"):
                address = cell.attrib["r"]
                if address not in expected[name]:
                    continue
                raw = cell.findtext(namespace + "v")
                kind = cell.attrib.get("t", "n")
                if kind == "s":
                    value = strings[int(raw)] if raw is not None else None
                elif kind == "inlineStr":
                    node = cell.find(namespace + "is")
                    value = "".join(node.itertext()) if node is not None else None
                elif kind == "b":
                    value = "True" if raw == "1" else "False"
                else:
                    value = raw
                actual = expected[name][address]
                issue = issues.get((name, address))
                if issue is not None:
                    matches = (
                        kind == "n"
                        and actual is None
                        and Decimal(value) == Decimal(issue["source_excel_serial"])
                    )
                elif kind == "n" and value is not None and actual is not None:
                    matches = Decimal(value) == Decimal(actual)
                else:
                    matches = value == actual or (value is None and actual == "")
                if not matches:
                    raise ValueError(f"Workbook XML value mismatch: {name}!{address}")
                observed.add(address)
                checked += 1
            if any(
                value is not None
                for address, value in expected[name].items()
                if address not in observed
            ):
                raise ValueError(f"Missing source XML cells in {name}")
    return {
        "method": "Independent worksheet XML and shared-string value comparison",
        "rows": len(rows),
        "present_cells_checked": checked,
    }


def extract_missions(root, source, recipe_path):
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    from openpyxl.utils.datetime import to_excel

    recipe = json.loads(recipe_path.read_text())
    if sha256(source) != recipe["source_sha256"]:
        raise ValueError("Unexpected mission workbook snapshot")
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        if workbook.sheetnames != list(recipe["sheet_roles"]):
            raise ValueError("Workbook sheets differ from the reviewed recipe")
        notice = recipe["reuse_notice"]
        value = workbook[notice["sheet"]][notice["cell"]].value
        if hashlib.sha256(str(value).encode()).hexdigest() != notice["sha256"]:
            raise ValueError("Workbook reuse notice differs from reviewed snapshot")
        aliases = {
            field: {label(alias) for alias in names}
            for field, names in recipe["field_aliases"].items()
        }
        withheld_labels = {label(name) for name in recipe["withheld_headers"]}
        rows, sheets = [], []
        for sheet in workbook:
            role = recipe["sheet_roles"][sheet.title]
            header = None
            positions = {}
            withheld = {}
            included = 0
            populated = 0
            last_row = 0
            names = set()
            omitted_cells = collections.Counter()
            absent_fields = collections.Counter()
            dispositions = collections.Counter()
            for row_number, values in enumerate(sheet.iter_rows(values_only=True), 1):
                last_row = row_number
                if not any(value is not None for value in values):
                    dispositions["empty_row"] += 1
                    continue
                populated += 1
                if role not in ENTRY_ROLES:
                    dispositions["non_entry_worksheet_row"] += 1
                    continue
                if header is None:
                    labels = {
                        label(value): column
                        for column, value in enumerate(values)
                        if value is not None
                    }
                    proposed = {
                        field: next(
                            (labels[name] for name in names if name in labels), None
                        )
                        for field, names in aliases.items()
                    }
                    if proposed["mission_name"] is None or proposed["faction"] is None:
                        dispositions["before_header"] += 1
                        continue
                    positions = {
                        field: column
                        for field, column in proposed.items()
                        if column is not None
                    }
                    withheld = {
                        column: str(values[column])
                        for name, column in labels.items()
                        if name in withheld_labels
                    }
                    header = row_number
                    dispositions["header"] += 1
                    continue
                title = (
                    values[positions["mission_name"]]
                    if len(values) > positions["mission_name"]
                    else None
                )
                if title is None or not str(title).strip():
                    dispositions["no_mission_name"] += 1
                    continue
                if label(title) in aliases["mission_name"]:
                    dispositions["repeated_header"] += 1
                    continue
                if str(title) in {"#REF!", "#N/A", "#VALUE!", "#ERROR!"}:
                    raise ValueError(
                        f"Unresolved mission-name cell: {sheet.title}, row {row_number}"
                    )
                facts = {}
                cell_issues = []
                for field, column in positions.items():
                    value = values[column] if column < len(values) else None
                    if isinstance(value, (date, time, timedelta)):
                        facts[field] = None
                        cell_issues.append(
                            {
                                "field": field,
                                "cell": get_column_letter(column + 1) + str(row_number),
                                "reason": "date_formatted_non_date_metadata",
                                "source_excel_serial": str(
                                    to_excel(value, workbook.epoch)
                                ),
                            }
                        )
                    else:
                        facts[field] = scalar(value)
                cells = {
                    field: get_column_letter(column + 1) + str(row_number)
                    for field, column in positions.items()
                }
                withheld_cells = []
                for column, name in withheld.items():
                    value = values[column] if column < len(values) else None
                    if value is not None and str(value).strip():
                        omitted_cells[name] += 1
                        withheld_cells.append(
                            {
                                "cell": get_column_letter(column + 1) + str(row_number),
                                "field": name,
                                "sha256": hashlib.sha256(
                                    str(value).encode()
                                ).hexdigest(),
                            }
                        )
                for field in positions:
                    if facts[field] is None:
                        absent_fields[field] += 1
                text = "\n".join(
                    field.replace("_", " ").capitalize() + " — " + value
                    for field, value in facts.items()
                    if value is not None and value.strip()
                )
                rows.append(
                    {
                        "record_id": "exarch:"
                        + recipe["source_sha256"][:12]
                        + ":"
                        + sheet.title
                        + ":"
                        + str(row_number),
                        "title": str(title).strip(),
                        "text": text,
                        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "source_url": recipe["source_url"],
                        "source_workbook_sha256": recipe["source_sha256"],
                        "source_sheet": sheet.title,
                        "source_row": row_number,
                        "source_cells": cells,
                        "source_role": role,
                        "mission_metadata": facts,
                        "withheld_source_cells": withheld_cells,
                        "source_cell_issues": cell_issues,
                        "license": "Nonstandard author reuse invitation for attributed factual metadata; underlying game content rights remain separate",
                        "license_evidence": "catalog/sources/exarch-workbook-recipe.json",
                        "attribution": recipe["attribution"],
                        "evidence_class": "secondary_mission_metadata",
                        "coverage": "One source checklist row. Mission identity, unique game mission counts, completeness, narrative content and current game applicability remain unverified.",
                        "embedded": False,
                    }
                )
                included += 1
                names.add(str(title))
                dispositions["included_entry"] += 1
            if role in ENTRY_ROLES and header is None:
                raise ValueError(f"Missing reviewed mission header in {sheet.title}")
            sheets.append(
                {
                    "sheet": sheet.title,
                    "role": role,
                    "last_xml_row": last_row,
                    "populated_rows": populated,
                    "header_row": header,
                    "included_entries": included,
                    "distinct_source_titles": len(names),
                    "withheld_nonempty_cells": dict(omitted_cells),
                    "missing_metadata_fields": dict(absent_fields),
                    "row_dispositions": dict(dispositions),
                }
            )
    finally:
        workbook.close()
    independent_validation = verify_source_cells(source, rows)
    payloads = collections.Counter(
        json.dumps(row["mission_metadata"], sort_keys=True) for row in rows
    )
    report = {
        "schema_version": 1,
        "scope": "All reviewed source checklist worksheets plus the legacy backup, preserving row occurrences and source roles. Counts describe source entries and title strings.",
        "source_url": recipe["source_url"],
        "source_workbook_sha256": recipe["source_sha256"],
        "recipe_sha256": sha256(recipe_path),
        "extractor_sha256": sha256(Path(__file__)),
        "sheets": sheets,
        "source_cell_validation": independent_validation,
        "counts": {
            "worksheets": len(sheets),
            "entry_worksheets": sum(sheet["role"] in ENTRY_ROLES for sheet in sheets),
            "included_entries": len(rows),
            "unresolved_metadata_cells": sum(
                len(row["source_cell_issues"]) for row in rows
            ),
            "by_role": dict(collections.Counter(row["source_role"] for row in rows)),
            "exact_repeated_metadata_occurrences": sum(
                value - 1 for value in payloads.values()
            ),
        },
        "limitations": [
            "Source entries can overlap across worksheets, contexts and historical versions. These counts do not establish unique game missions.",
            "The Combined worksheet has a source formula error and missing mission identities. Its helper reward values require separate reconciliation.",
            "Narrative descriptions, notes and workbook media remain outside this factual metadata extraction.",
            "The author reuse invitation is nonstandard. Original game prose and media rights and current game completeness remain unresolved.",
        ],
    }
    output = root / recipe["output_data"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".jsonl.tmp")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        )
    )
    report["output_sha256"] = sha256(temporary)
    temporary.replace(output)
    audit = root / recipe["output_audit"]
    audit.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report["counts"]))


def verify_mission_metadata(root):
    recipe = json.loads(
        (root / "catalog/sources/exarch-workbook-recipe.json").read_text()
    )
    report_path = root / "catalog/sources/exarch-workbook-extraction.json"
    if not report_path.exists():
        report_path = root / "evaluation/exarch-workbook-extraction.json"
    report = json.loads(report_path.read_text())
    data = root / "data/exarch-mission-metadata.jsonl"
    if (
        sha256(data) != report["output_sha256"]
        or sha256(root / "catalog/sources/exarch-workbook-recipe.json")
        != report["recipe_sha256"]
    ):
        raise ValueError("Mission source recipe or data hash mismatch")
    roles = collections.Counter()
    sheet_counts = collections.Counter()
    names = collections.defaultdict(set)
    metadata = collections.Counter()
    identifiers = set()
    unresolved = 0
    with data.open() as stream:
        for line in stream:
            row = json.loads(line)
            sheet, number = row["source_sheet"], row["source_row"]
            if (
                sheet not in recipe["sheet_roles"]
                or row["source_role"] != recipe["sheet_roles"][sheet]
                or row["source_role"] not in ENTRY_ROLES
            ):
                raise ValueError("Unreviewed mission worksheet role")
            expected_id = (
                "exarch:"
                + recipe["source_sha256"][:12]
                + ":"
                + sheet
                + ":"
                + str(number)
            )
            if row["record_id"] != expected_id or expected_id in identifiers:
                raise ValueError("Mission source-row identity mismatch")
            identifiers.add(expected_id)
            facts = row["mission_metadata"]
            if not set(facts).issubset(recipe["field_aliases"]) or set(facts) != set(
                row["source_cells"]
            ):
                raise ValueError("Unexpected mission metadata fields")
            expected_lines = []
            for field in recipe["field_aliases"]:
                value = facts.get(field)
                if value is not None and value.strip():
                    expected_lines.append(
                        field.replace("_", " ").capitalize() + " — " + value
                    )
            expected_text = "\n".join(expected_lines)
            if (
                row["text"] != expected_text
                or hashlib.sha256(row["text"].encode()).hexdigest()
                != row["text_sha256"]
            ):
                raise ValueError("Mission metadata text mismatch")
            if (
                row["source_workbook_sha256"] != recipe["source_sha256"]
                or row["source_url"] != recipe["source_url"]
                or row["title"] != facts["mission_name"].strip()
            ):
                raise ValueError("Mission workbook provenance mismatch")
            for address in row["source_cells"].values():
                if (
                    not address.rstrip("0123456789").isalpha()
                    or address.rstrip("0123456789") + str(number) != address
                ):
                    raise ValueError("Mission source-cell reference mismatch")
            for issue in row["source_cell_issues"]:
                if (
                    issue["field"] not in facts
                    or facts[issue["field"]] is not None
                    or row["source_cells"][issue["field"]] != issue["cell"]
                ):
                    raise ValueError("Unresolved mission metadata cell mismatch")
            unresolved += len(row["source_cell_issues"])
            roles[row["source_role"]] += 1
            sheet_counts[sheet] += 1
            names[sheet].add(facts["mission_name"])
            metadata[json.dumps(facts, sort_keys=True)] += 1
    counts = report["counts"]
    if (
        len(identifiers) != counts["included_entries"]
        or dict(roles) != counts["by_role"]
        or unresolved != counts["unresolved_metadata_cells"]
    ):
        raise ValueError("Mission metadata population mismatch")
    if (
        sum(value - 1 for value in metadata.values())
        != counts["exact_repeated_metadata_occurrences"]
    ):
        raise ValueError("Mission metadata repetition count mismatch")
    if [sheet["sheet"] for sheet in report["sheets"]] != list(recipe["sheet_roles"]):
        raise ValueError("Mission worksheet inventory mismatch")
    for sheet in report["sheets"]:
        if (
            sheet_counts[sheet["sheet"]] != sheet["included_entries"]
            or len(names[sheet["sheet"]]) != sheet["distinct_source_titles"]
        ):
            raise ValueError("Mission worksheet count mismatch")
        if sum(sheet["row_dispositions"].values()) != sheet["last_xml_row"]:
            raise ValueError("Mission worksheet row accounting mismatch")
    if report["source_cell_validation"]["rows"] != len(identifiers):
        raise ValueError("Mission source-cell validation scope mismatch")
    return len(identifiers)
