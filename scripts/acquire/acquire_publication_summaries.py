"""Recover title-matched Old Republic publication and related wiki articles.

This is a bounded discovery pass over a pinned independent snapshot, not a
complete publication census. Source continuity is not a structured field.
"""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
from wiki_rights_filter import requires_review, is_held_url

REPO='thehackersbrain/star-wars-dataset'
REV='7c5ca7523196d9f460f1a5ff980f57855c59bb01'
FILE='data/train-00000-of-00001.parquet'
PAT=re.compile(r'knights of the old republic|the old republic|tales of the jedi|dawn of the jedi|knight errant|jedi vs\. sith|lost tribe of the sith',re.I)
def key(url):return unquote(url).replace(' ','_').lower()
existing=set()
for file in ('data/wookieepedia-legends.parquet','data/wookieepedia-era-supplement.parquet','data/wookieepedia-reference-supplement.parquet'):
 existing.update(key(url) for url in pq.read_table(file,columns=['url'])['url'].to_pylist() if url)
with open('data/wookieepedia-comic-summaries.jsonl',encoding='utf-8') as f:
 existing.update(key(json.loads(line)['url']) for line in f)
path=hf_hub_download(REPO,FILE,repo_type='dataset',revision=REV)
found={}
for batch in pq.ParquetFile(path).iter_batches(batch_size=2000):
 for x in batch.to_pylist():
  title=x['title'] or '';url=x['url'] or ''
  if not url or is_held_url(url) or not PAT.search(title) or key(url) in existing or requires_review(x['text']):continue
  if key(url) in found:raise ValueError('duplicate normalized URL: '+url)
  if x['license']!='CC BY-SA 3.0' or x['source']!='Wookieepedia':raise ValueError('unexpected source or license')
  x['sha256']=hashlib.sha256(x['text'].encode()).hexdigest()
  x['upstream_repository']=REPO;x['upstream_revision']=REV;x['evidence_class']='secondary';x['continuity']='unclassified'
  x['selection_terms']=sorted({m.group(0).lower() for m in PAT.finditer(title)})
  found[key(url)]=x
out=Path('data/wookieepedia-publication-summaries.jsonl')
with out.open('w',encoding='utf-8',newline='\n') as f:
 for k in sorted(found):f.write(json.dumps(found[k],ensure_ascii=False,sort_keys=True)+'\n')
print(json.dumps({'articles':len(found),'selection':PAT.pattern,'upstream_revision':REV}))
