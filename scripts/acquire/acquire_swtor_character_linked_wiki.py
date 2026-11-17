"""Recover five manually reviewed SWTOR character-linked Legends articles.

The pinned upstream snapshot lacks original wiki revision identifiers. Screens
are conservative discovery signals, not proof that unmarked excerpts are clear.
No inference or model call is performed.
"""
import hashlib,re
from pathlib import Path
import pyarrow as pa,pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
from wiki_rights_filter import requires_review
REPO='rafa-rrayes/wookieelm-corpus';REV='5d19bba512fa8c65b225c1819d7971db316b871c'
PINS={'wookieepedia/B/Bolgm.md':'1caeddce764068cf24c90dc91b195f31defd6dd01beb379cd3b3779e97490e93','wookieepedia/L/Lylos_Tannon.md':'554fb4d088912d6763c7d0cfcbd1eb078a4e77beddc8349aef61fbfd8353736b','wookieepedia/P/Pova.md':'22114ed37d78a64c42829ca2b7deeb6a5a57312995cd83a933386e9c693404b2','wookieepedia/V/Varko_(Selkath).md':'1a1c97433261288737410092f33230fedb111a697a704052d1324ebd4f78ae64','wookieepedia/Z/Zeke.md':'4dad5fc09c6869f58b59d98e5aec4d2944a124d94e9b0f8d2433fffd99b72f60'}
rows=[]
for i in range(2):
 p=hf_hub_download(REPO,f'pretrain/wookieepedia-{i:05d}-of-00002.parquet',repo_type='dataset',revision=REV)
 for batch in pq.ParquetFile(p).iter_batches(batch_size=500):
  for r in batch.to_pylist():
   if r.get('doc_id') not in PINS:continue
   text=r.get('text') or '';digest=hashlib.sha256(text.encode()).hexdigest()
   if digest!=PINS[r['doc_id']] or r.get('continuity')!='legends' or r.get('license')!='CC BY-SA 3.0' or requires_review(text) or re.search(r'["“”]|(?m:^\s*>)',text):raise ValueError('changed or unsuitable source: '+r['doc_id'])
   r.update(sha256=digest,upstream_revision=REV,evidence_class='secondary',coverage='Character-linked SWTOR-related secondary wiki article; original revision and unmarked third-party excerpts are not independently verified.',embedded=False);rows.append(r)
if len(rows)!=len(PINS) or len({r['doc_id'] for r in rows})!=len(PINS):raise ValueError('missing or duplicate records')
rows.sort(key=lambda r:r['doc_id']);pq.write_table(pa.Table.from_pylist(rows),'data/wookieepedia-swtor-character-linked.parquet',compression='zstd');print('Selected',len(rows),'unembedded secondary articles')
