"""Run corpus tools with a consistent repository root and verify releases."""
import argparse
import hashlib
import json
import os
import runpy
import sys
from importlib.metadata import entry_points
from pathlib import Path


def project_root():
    root = Path(os.environ.get('HOLOVEC_ROOT', Path(__file__).resolve().parents[2]))
    if not (root / 'manifest.json').is_file():
        raise SystemExit('Set HOLOVEC_ROOT to a HoloVec checkout containing manifest.json.')
    return root


def verify(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    failures = []
    entries = manifest['input_files'] + manifest['vector_files']
    for entry in entries:
        path = root / entry['path']
        if not path.is_file():
            failures.append(f'Missing {entry["path"]}')
            continue
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if path.stat().st_size != entry['size'] or digest != entry['sha256']:
            failures.append(f'Changed {entry["path"]}')
    paths = [entry['path'] for entry in entries]
    if len(paths) != len(set(paths)):
        failures.append('Duplicate manifest paths')
    from .cards import card_metadata
    metadata = card_metadata(root)
    configurations = metadata.get('configs', [])
    names = [config['config_name'] for config in configurations]
    if len(names) != len(set(names)):
        failures.append('Duplicate dataset configuration names')
    for config in configurations:
        for relative in dataset_paths(config['data_files']):
            if Path(relative).is_absolute() or '..' in Path(relative).parts:
                failures.append(f'Invalid dataset configuration path {relative}')
            elif not any(path.is_file() for path in root.glob(relative)):
                failures.append(f'Missing dataset configuration file {relative}')
    import pyarrow.parquet as pq
    coverage = json.loads((root / 'unified/coverage.json').read_text())
    rows = pq.ParquetFile(root / 'unified/corpus.parquet').metadata.num_rows
    if rows != coverage['rows'] or rows != manifest['counts']['unified_text_records']:
        failures.append('Unified corpus row count mismatch')
    if (root / 'catalog/games/resource-census.json').exists():
        from .game_inventory import verify_census
        verify_census(root)
    if (root / 'catalog/games/distribution-verification.json').exists():
        from .steam_inventory import verify_comparison
        verify_comparison(root)
    if any((root / path).exists() for path in (
        'catalog/sources/exarch-workbook-extraction.json',
        'evaluation/exarch-workbook-extraction.json',
    )):
        from .mission_inventory import verify_mission_metadata
        verify_mission_metadata(root)
    if (root / 'catalog/games/dialogue-census.json').exists():
        from .dialogue_inventory import verify_dialogues
        verify_dialogues(root)
    if (root / 'catalog/games/journal-census.json').exists():
        from .journal_inventory import verify_journals
        verify_journals(root)
    if (root / 'catalog/sources/original-documents.json').exists():
        verify_original_documents(root, manifest)
    if failures:
        raise SystemExit('\n'.join(failures))
    print(f'Verified {len(entries)} files and {rows:,} text records.')


def verify_original_documents(root, manifest):
    """Check original-document provenance against release pins and the registry."""
    catalog_path = 'catalog/sources/original-documents.json'
    catalog = json.loads((root / catalog_path).read_text())
    registry = json.loads((root / 'catalog/sources/source-inventory.json').read_text())
    sources = {source['id']: source for source in registry}
    pins = {entry['path']: entry for entry in manifest['input_files']}
    if catalog_path not in pins:
        raise ValueError('Original-document catalog is missing from the manifest')
    if len(catalog['documents']) != manifest['counts']['original_documents']:
        raise ValueError('Original-document count mismatch')
    if sum(document['pages'] for document in catalog['documents']) != manifest['counts']['original_document_pages']:
        raise ValueError('Original-document page count mismatch')
    seen = set()
    for document in catalog['documents']:
        relative = document['path']
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError(f'Unsafe original-document path: {relative}')
        if relative in seen:
            raise ValueError(f'Duplicate original-document path: {relative}')
        seen.add(relative)
        pin = pins.get(relative)
        if pin is None or any(pin[key] != document[key] for key in ('size', 'sha256')):
            raise ValueError(f'Original-document manifest mismatch: {relative}')
        license_pin = pins.get(document['license_path'])
        if license_pin is None or license_pin['sha256'] != document['license_text_sha256']:
            raise ValueError(f'Original-document license mismatch: {relative}')
        source = sources.get(document['source_inventory_id'])
        if source is None or source.get('original_document') != relative:
            raise ValueError(f'Original-document registry mismatch: {relative}')


def dataset_paths(value):
    """Yield Hub file patterns from string, list and split/path declarations."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from dataset_paths(item)
    elif isinstance(value, dict) and 'path' in value:
        yield from dataset_paths(value['path'])
    else:
        raise ValueError(f'Unsupported dataset file declaration {value!r}')


def recipe_jobs(root):
    jobs = {}
    for path in sorted((root / 'scripts').glob('*/*.py')):
        if path.parent.name == 'shared':
            continue
        if path.stem in jobs:
            raise ValueError(f'Duplicate recipe name {path.stem!r}')
        jobs[path.stem] = path
    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('verify', help='Verify release files against the manifest')
    commands.add_parser('jobs', help='List preserved acquisition and review recipes')
    card = commands.add_parser('export-card', help='Write a platform dataset card')
    card.add_argument('--output', type=Path, required=True)
    github = commands.add_parser('acquire-github', help='Stage pinned, reviewed repository documents')
    github.add_argument('repository')
    missions = commands.add_parser('acquire-missions', help='Stage factual mission metadata from a pinned workbook')
    missions.add_argument('source', type=Path)
    missions.add_argument('--recipe', type=Path)
    inventory = commands.add_parser('inventory-games', help='Stage local game resource-header metadata')
    inventory.add_argument('--installation', nargs=2, action='append', required=True, metavar=('GAME', 'ROOT'))
    inventory.add_argument('--output', type=Path)
    dialogues = commands.add_parser('inventory-dialogues', help='Stage static conversation graphs from indexed game resources')
    dialogues.add_argument('--installation', nargs=2, action='append', required=True, metavar=('GAME', 'ROOT'))
    dialogues.add_argument('--output', type=Path)
    journals = commands.add_parser('inventory-journals', help='Stage journal metadata and dialogue quest references')
    journals.add_argument('--installation', nargs=2, action='append', required=True, metavar=('GAME', 'ROOT'))
    journals.add_argument('--output', type=Path)
    steam = commands.add_parser('compare-steam', help='Stage file hashes against a cached Steam depot manifest')
    steam.add_argument('--appmanifest', type=Path, required=True)
    steam.add_argument('--depot-manifest', type=Path, required=True)
    steam.add_argument('--installation', nargs=2, action='append', required=True, metavar=('LABEL', 'ROOT'))
    steam.add_argument('--output', type=Path)
    coverage = commands.add_parser('coverage', help='Reconcile source registry URLs with released records')
    coverage.add_argument('--output', type=Path)
    run = commands.add_parser('run', help='Run a recipe from the repository root')
    run.add_argument('job')
    run.add_argument('arguments', nargs=argparse.REMAINDER)
    search = commands.add_parser('search', help='Search the corpus without model inference')
    search.add_argument('arguments', nargs=argparse.REMAINDER)
    for provider in entry_points(group='holovec.commands'):
        provider.load()(commands)
    args = parser.parse_args()
    root = project_root()
    if args.command == 'export-card':
        from .cards import render_card
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_card(root))
        return
    if getattr(args, 'handler', None):
        args.handler(args, root)
        return
    if args.command == 'inventory-journals':
        from .journal_inventory import inventory_journals
        inventory_journals(root, args.installation, args.output or root / 'staging/game-journal-census')
        return
    if args.command == 'inventory-dialogues':
        from .dialogue_inventory import inventory_dialogues
        inventory_dialogues(root, args.installation, args.output or root / 'staging/game-dialogue-census')
        return
    if args.command == 'acquire-missions':
        from .mission_inventory import extract_missions
        extract_missions(root, args.source, args.recipe or root / 'catalog/sources/exarch-workbook-recipe.json')
        return
    if args.command == 'compare-steam':
        from .steam_inventory import compare_steam
        compare_steam(args.appmanifest, args.depot_manifest, args.installation, args.output or root / 'staging/steam-comparison')
        return
    if args.command == 'inventory-games':
        from .game_inventory import inventory_games
        inventory_games(args.installation, args.output or root / 'staging/game-resource-census')
        return
    if args.command == 'acquire-github':
        from .github import stage_documents
        stage_documents(root, args.repository)
        return
    if args.command == 'coverage':
        from .coverage import source_coverage
        source_coverage(root, args.output or root / 'staging/working-records/source-catalog-coverage.json')
        return
    if args.command == 'verify':
        verify(root)
        return
    jobs = recipe_jobs(root)
    if args.command == 'jobs':
        print('\n'.join(sorted(jobs)))
        return
    name = 'search_corpus' if args.command == 'search' else args.job.removesuffix('.py')
    if name not in jobs:
        parser.error(f'Unknown recipe {name!r}. Run holovec jobs for available names.')
    os.chdir(root)
    sys.path.insert(0, str(root / 'scripts/shared'))
    sys.path.insert(0, str(jobs[name].parent))
    sys.argv = [str(jobs[name]), *args.arguments]
    runpy.run_path(str(jobs[name]), run_name='__main__')
