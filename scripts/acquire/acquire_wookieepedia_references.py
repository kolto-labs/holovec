"""Supplement the existing keyword snapshot with reference-selected Legends articles.

Input is the independently published WookieeLM snapshot, not the private Trask archive.
Reference matching is deliberately bounded and does not assert exhaustive coverage.
"""
import hashlib
import json
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

REV = '5d19bba512fa8c65b225c1819d7971db316b871c'
SOURCE = 'rafa-rrayes/wookieelm-corpus'
PAT = re.compile(r'\b(?:Great Hyperspace War|Great Sith War|Jedi Civil War|Mandalorian Wars|Sith Triumvirate|Great Galactic War|Exar Kun|Ulic Qel-Droma|Nomi Sunrider|Zayne Carrick|Naga Sadow|Ludo Kressh|Meetra Surik|Darth Nihilus|Darth Sion|Darth Traya|Darth Malak|Bastila Shan|Darth Revan|Satele Shan|Darth Malgus|Vitiate|Tenebrae)\b', re.I)
existing = set()
for file in ('data/wookieepedia-legends.parquet', 'data/wookieepedia-era-supplement.parquet'):
    existing.update(pq.read_table(file, columns=['doc_id'])['doc_id'].to_pylist())
rows = []
for i in range(2):
    path = hf_hub_download(SOURCE, f'pretrain/wookieepedia-{i:05d}-of-00002.parquet', repo_type='dataset', revision=REV)
    for batch in pq.ParquetFile(path).iter_batches(batch_size=1000):
        for x in batch.to_pylist():
            matched = sorted({m.group(0).lower() for m in PAT.finditer(x['text'] or '')})
            if x['continuity'] != 'legends' or x['doc_id'] in existing or not matched:
                continue
            x['sha256'] = hashlib.sha256(x['text'].encode()).hexdigest()
            x['upstream_revision'] = REV
            x['evidence_class'] = 'secondary'
            x['selection_references'] = matched
            rows.append(x)
rows.sort(key=lambda x: x['doc_id'])
if len({r['doc_id'] for r in rows}) != len(rows):
    raise ValueError('duplicate doc_id in selected input')
Path('data').mkdir(exist_ok=True)
pq.write_table(pa.Table.from_pylist(rows), 'data/wookieepedia-reference-supplement.parquet', compression='zstd')
print(json.dumps({'documents': len(rows), 'selection': PAT.pattern, 'upstream_revision': REV}))
