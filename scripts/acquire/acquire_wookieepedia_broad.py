"""Select a broad reference layer from a separately published Wookieepedia snapshot.

A text mention can be incidental, ambiguous, or a citation; continuity is not
provided in this snapshot. A deterministic URL comparison prevents overlap with
previous wiki selections. It does not establish complete or primary coverage.
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
PAT=re.compile(r'\b(?:Knights of the Old Republic|The Old Republic|Tales of the Jedi|Great Hyperspace War|Great Sith War|Jedi Civil War|Mandalorian Wars|Great Galactic War|Sith Triumvirate|Zayne Carrick|Naga Sadow|Darth Nihilus|Bastila Shan)\b',re.I)
def key(url):return unquote(url).replace(' ','_')
existing=set()
for file in ('data/wookieepedia-legends.parquet','data/wookieepedia-era-supplement.parquet','data/wookieepedia-reference-supplement.parquet'):
 existing.update(key(url) for url in pq.read_table(file,columns=['url'])['url'].to_pylist() if url)
for file in ('data/wookieepedia-comic-summaries.jsonl','data/wookieepedia-publication-summaries.jsonl'):
 with open(file,encoding='utf-8') as f:existing.update(key(json.loads(line)['url']) for line in f)
path=hf_hub_download(REPO,FILE,repo_type='dataset',revision=REV)
found=set();count=0
with Path('data/wookieepedia-broad-references.jsonl').open('w',encoding='utf-8',newline='\n') as out:
 for batch in pq.ParquetFile(path).iter_batches(batch_size=2000):
  for x in batch.to_pylist():
   url=x['url'] or '';text=x['text'] or ''
   if not url or is_held_url(url) or key(url) in existing or requires_review(text):continue
   matched=sorted({m.group().lower() for m in PAT.finditer(text)})
   if not matched:continue
   if key(url) in found:raise ValueError('duplicate normalized URL: '+url)
   if x['source']!='Wookieepedia' or x['license']!='CC BY-SA 3.0':raise ValueError('unexpected source or license')
   x.update(sha256=hashlib.sha256(text.encode()).hexdigest(),upstream_repository=REPO,upstream_revision=REV,evidence_class='secondary',continuity='unclassified',selection_terms=matched)
   out.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n');found.add(key(url));count+=1
print(json.dumps({'articles':count,'selection':PAT.pattern,'upstream_revision':REV}))
