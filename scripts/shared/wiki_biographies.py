"""Extract pinned wiki sections with shared attribution and quotation screening."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote

import mwparserfromhell

HEADINGS = re.compile(r'(?m)^(={2,6})\s*(.*?)\s*\1\s*$')
QUOTE_TEMPLATES = {'quote', 'quotation', 'blockquote', 'quote box', 'dialogue', 'speech', 'cquote', 'quote frame'}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def shingles(text):
    words = re.findall(r'\w+', text.casefold())
    return {tuple(words[index:index + 8]) for index in range(max(0, len(words) - 7))}


def quoted_sequences(page):
    values = []
    for template in page.filter_templates(recursive=True):
        name = str(template.name).strip().casefold().replace('_', ' ')
        for parameter in template.params:
            if name in QUOTE_TEMPLATES or str(parameter.name).strip().casefold() in {'quote', 'quotation'}:
                values.append(mwparserfromhell.parse(str(parameter.value)).strip_code(normalize=True, collapse=True))
    for tag in page.filter_tags(recursive=True):
        if str(tag.tag).casefold() in {'blockquote', 'q'}:
            values.append(mwparserfromhell.parse(str(tag.contents)).strip_code(normalize=True, collapse=True))
    return set().union(*(shingles(value) for value in values)) if values else set()


def clean_section(source, quotations):
    code = mwparserfromhell.parse(source)
    nodes = [tag for tag in code.filter_tags(recursive=True)
             if str(tag.tag).casefold() in {'ref', 'references', 'gallery', 'blockquote', 'q'}]
    nodes += [link for link in code.filter_wikilinks(recursive=True)
              if str(link.title).strip().casefold().startswith(('file:', 'image:'))]
    nodes += list(code.filter_templates(recursive=False))
    for node in nodes:
        try:
            code.remove(node, recursive=True)
        except ValueError:
            pass
    text = code.strip_code(normalize=True, collapse=True).strip()
    text, omitted_quotes = re.subn(r'["“][^"“”\n]{1,300}["”]', '[quoted words omitted]', text)
    paragraphs = []
    omitted_paragraphs = 0
    for paragraph in re.split(r'\n\s*\n', text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if re.search(r'["“”]', paragraph) or shingles(paragraph) & quotations:
            omitted_paragraphs += 1
        else:
            paragraphs.append(paragraph)
    return '\n\n'.join(paragraphs), omitted_quotes, omitted_paragraphs


def run_recipe(name):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output-root', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    recipe = json.loads((root / 'catalog/biography-recipes.json').read_text())[name]
    sources = json.loads(args.source.read_text())
    if recipe['wrapped_source']:
        sources = {title: {'id': value['revision_id'], 'timestamp': value['timestamp'], 'raw': value['raw_wikitext']}
                   for title, value in sources['records'].items()}
    rows, held = [], []
    for subject, (revision, expected_digest, sections) in recipe['sources'].items():
        document = sources[subject]
        raw = document['raw']
        if document['id'] != revision or digest(raw) != expected_digest:
            raise ValueError(f'Unexpected source revision for {subject}')
        quotations = quoted_sequences(mwparserfromhell.parse(raw))
        headings = list(HEADINGS.finditer(raw))
        for section in sections:
            matches = [(index, heading) for index, heading in enumerate(headings) if heading.group(2) == section]
            if len(matches) != 1:
                raise ValueError(f'Section mismatch for {subject}/{section}')
            index, heading = matches[0]
            following = headings[index + 1:]
            if recipe['include_subsections']:
                following = [item for item in following if len(item.group(1)) <= len(heading.group(1))]
            end = following[0].start() if following else len(raw)
            source = raw[heading.end():end]
            text, omitted_quotes, omitted_paragraphs = clean_section(source, quotations)
            if not text:
                held.append({'title': subject, 'section': section, 'reason': 'empty after review'})
                continue
            url = 'https://starwars.fandom.com/wiki/' + quote(subject.replace(' ', '_'))
            rows.append({**recipe['constants'], **recipe.get('source_metadata', {}).get(subject, {}), 'title': subject + ' — ' + section.replace("''", ''),
                         'section': section.replace("''", ''), 'subject': subject, 'url': url, 'source_url': url,
                         'source_revision_url': url + '?oldid=' + revision, 'revision_id': revision,
                         'timestamp': document['timestamp'], 'source_page_wikitext_sha256': expected_digest,
                         'section_wikitext_sha256': digest(source), 'text': text, 'text_sha256': digest(text),
                         'omitted_inline_quotations': omitted_quotes, 'omitted_paragraphs': omitted_paragraphs})
    audit = {'description': 'Limited marked-quotation screen; not primary source or complete rights clearance.',
             'source_archive_sha256': 'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456',
             'included': len(rows), 'held_sections': held,
             'omitted_paragraphs': sum(row['omitted_paragraphs'] for row in rows),
             'omitted_inline_quotations': sum(row['omitted_inline_quotations'] for row in rows),
             'items': [{'title': row['title'], 'revision_id': row['revision_id'], 'text_sha256': row['text_sha256']} for row in rows]}
    destination = args.output_root or root
    data_path = destination / recipe['data_path']
    audit_path = destination / recipe.get(
        'audit_path', f'staging/working-records/reports/{name}.json'
    )
    data_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows))
    audit_path.write_text(json.dumps(audit, indent=2) + '\n')
    print(f'Extracted {len(rows)} sections with recipe {name}.')
