"""Reproduce marker-reviewed Sith Empire category records from pinned WookieeLM.

Whole-text marker screening is limited, not a rights clearance. These seven records had quote markers reviewed as names or short terms. No inference is performed.
"""
import hashlib,json,re
from pathlib import Path
import pyarrow as pa,pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
REV='5d19bba512fa8c65b225c1819d7971db316b871c';REPO='rafa-rrayes/wookieelm-corpus'
PINS={'wookieepedia/A/Arljack.md': '8c0d848857d1bf174bfe94440362be2c0697dd03e6b9755fab8179d2fbf11652', 'wookieepedia/B/Battle_of_Kalandis_Seven.md': 'b5af6ef070318fa216e8e6e28009c5cae2a15fb6fec4dc815b6603c1a2567822', 'wookieepedia/D/Darth_Drear.md': '17027ed800dd1e84a9f3707a3ffc4afd011e5d02fc8494c64e3e66c565574530', "wookieepedia/D/Darth_Scabrous'_HK_droid.md": '68cc27325f3f7285a294b92843f3e34172d3bea27b5e3986b48fa1e8757a38c1', 'wookieepedia/I/Imperial_Citizenship_Bureau.md': '11566a3d8adaf945faf0f563ad14a09eae5310055aa4c5f7dcf8aa77a7ffdf91', "wookieepedia/J/Jaguada's_moon.md": '06addfe41369a8b16f786e05d58257b293f6ddcce1314b7246f7ad9be26b989c', 'wookieepedia/N/Ninûshwodzakut.md': 'c0d2082774955b85826b7f8cdff438e9a3b57dea9040c4a08764124be0e4ed54'}
PAT=re.compile(r'(?i)\bsith empire\b|\breconstituted sith empire\b|\bresurgent sith empire\b|\bbattles of the galactic war\b')
rows=[]
for i in range(2):
 path=hf_hub_download(REPO,f'pretrain/wookieepedia-{i:05d}-of-00002.parquet',repo_type='dataset',revision=REV)
 for batch in pq.ParquetFile(path).iter_batches(batch_size=1000):
  for x in batch.to_pylist():
   if x['doc_id'] not in PINS:continue
   text=x['text'] or '';digest=hashlib.sha256(text.encode()).hexdigest()
   if digest!=PINS[x['doc_id']] or x['continuity']!='legends' or re.search(r'(?m:^\s*>)',text):raise ValueError('source record changed or failed screening: '+x['doc_id'])
   cats=[c for c in x['categories'] or [] if PAT.search(c)]
   if not cats:raise ValueError('missing matched category')
   x.update(sha256=digest,upstream_revision=REV,evidence_class='secondary',selection_categories=cats);rows.append(x)
if len(rows)!=len(PINS) or len({r['doc_id'] for r in rows})!=len(PINS):raise ValueError('missing or duplicate records')
rows.sort(key=lambda x:x['doc_id']);pq.write_table(pa.Table.from_pylist(rows),'data/wookieepedia-sith-marker-reviewed.parquet',compression='zstd')
print('Selected',len(rows),'unembedded articles')
