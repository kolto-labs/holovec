"""Reconcile registered source URLs with the released corpus metadata."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pyarrow.parquet as pq


def normalized_url(url):
    parsed = urlsplit(url or '')
    host = parsed.netloc.casefold().removeprefix('www.')
    path = unquote(parsed.path).replace('_', ' ').rstrip('/').casefold()
    return host, path


def source_coverage(root, output):
    registry_path = root / 'catalog/sources/source-inventory.json'
    corpus_path = root / 'unified/corpus.parquet'
    manifest = json.loads((root / 'manifest.json').read_text())
    catalog_paths = ['catalog/sources/source-catalog.json', 'catalog/sources/upstream-source-catalog.json']
    for path in [registry_path, corpus_path, *(root / relative for relative in catalog_paths)]:
        relative = str(path.relative_to(root))
        entry = next(item for item in manifest['input_files'] if item['path'] == relative)
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != entry['sha256']:
                raise ValueError(f'Manifest mismatch for {relative}')
    registry = json.loads(registry_path.read_text())
    catalog_membership = defaultdict(list)
    for relative in catalog_paths:
        catalog = json.loads((root / relative).read_text())
        catalog_entries = catalog['entries'] if isinstance(catalog, dict) else catalog
        for entry in catalog_entries:
            catalog_membership[entry['id']].append(relative)
    missing = set(catalog_membership) - {entry['id'] for entry in registry}
    if missing:
        raise ValueError('Source registry omits catalog IDs: ' + ', '.join(sorted(missing)))
    records_by_host = defaultdict(list)
    layer_counts = defaultdict(int)
    for batch in pq.ParquetFile(corpus_path).iter_batches(
        columns=['source_layer', 'source_row', 'source_url', 'title', 'text_sha256']
    ):
        for record in batch.to_pylist():
            layer_counts[record['source_layer']] += 1
            host, path = normalized_url(record['source_url'])
            if host:
                records_by_host[host].append((path, record))
    def declared_layers(value):
        if isinstance(value, str):
            return {value} if value in layer_counts else set()
        if isinstance(value, dict):
            return set().union(*(declared_layers(item) for item in value.values()))
        if isinstance(value, (list, tuple)):
            return set().union(*(declared_layers(item) for item in value))
        return set()

    items = []
    for source in registry:
        host, path = normalized_url(source['url'])
        matches = [record for candidate, record in records_by_host[host]
                   if candidate == path or candidate.startswith(path + '/')]
        layers = sorted({record['source_layer'] for record in matches})
        items.append({'id': source['id'], 'name': source['name'], 'url': source['url'],
                      'registered_status': source['status'],
                      'catalog_membership': catalog_membership.get(source['id'], []),
                      'registered_ingested': source.get('ingested', False),
                      'declared_original_document': source.get('original_document'),
                      'matching_records': len(matches), 'matching_layers': layers,
                      'declared_text_layers': {layer: layer_counts[layer] for layer in sorted(declared_layers(source))},
                      'matched_urls': sorted({record['source_url'] for record in matches})})
    report = {
        'scope': 'Normalized host and path-prefix matches between source registry URLs and released record URLs. Declared text layers preserve explicit registry references, including related secondary material. Record presence is evidence of a URL relationship. Completeness, relevance, primary-content access, permissions, redirects and aliases require source-specific review.',
        'registry_sha256': hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        'corpus_sha256': next(item['sha256'] for item in manifest['input_files']
                              if item['path'] == 'unified/corpus.parquet'),
        'counts': {'registered_sources': len(items),
                   'required_catalog_ids': len(catalog_membership),
                   'required_catalog_ids_missing': len(missing),
                   'sources_with_matching_record_urls': sum(bool(item['matching_records']) for item in items),
                   'sources_without_matching_record_urls': sum(not item['matching_records'] for item in items),
                   'sources_with_declared_text_layers': sum(bool(item['declared_text_layers']) for item in items),
                   'sources_with_declared_original_documents': sum(bool(item['declared_original_document']) for item in items)},
        'items': items,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report['counts']))
