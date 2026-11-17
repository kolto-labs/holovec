"""Recover selected issue summaries from a separately published wiki snapshot.

The snapshot omits wiki revision IDs, may omit short articles, and is not a
source of comic pages. The issue map is partial; missing matches are reported.
"""
import hashlib
import json
from pathlib import Path
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
from wiki_rights_filter import requires_review

REPO='thehackersbrain/star-wars-dataset'
REV='7c5ca7523196d9f460f1a5ff980f57855c59bb01'
FILE='data/train-00000-of-00001.parquet'
TEMPLATES={
 'kotor-2006':'Knights of the Old Republic {n}',
 'kotor-war':'Knights of the Old Republic: War {n}',
 'totj-golden':'Tales of the Jedi – The Golden Age of the Sith {n}',
 'totj-fall':'Tales of the Jedi – The Fall of the Sith Empire {n}',
 'totj-1993':'Tales of the Jedi {n}',
 'totj-freedon':'Tales of the Jedi – The Freedon Nadd Uprising {n}',
 'totj-dark':'Tales of the Jedi – Dark Lords of the Sith {n}',
 'totj-sith-war':'Tales of the Jedi – The Sith War {n}',
 'totj-redemption':'Tales of the Jedi – Redemption {n}',
 'tor-2010':'The Old Republic {n}',
 'tor-lost-suns':'The Old Republic — The Lost Suns {n}',
 'lost-tribe-spiral':'Lost Tribe of the Sith — Spiral {n}',
 'knight-errant':'Knight Errant {n}',
 'knight-errant-deluge':'Knight Errant: Deluge {n}',
 'knight-errant-escape':'Knight Errant: Escape {n}',
 'jedi-vs-sith':'Jedi vs. Sith {n}',
}
inv=json.loads(Path('catalog/works/comics-issue-inventory.json').read_text())
expected={}
for issue in inv['issues']:
 key=issue['work_id'].rsplit('-',1)[0]
 if key in TEMPLATES:
  expected[TEMPLATES[key].format(n=issue['issue_number'])]=issue['work_id']
# Adjacent early Jedi works and #0s are recorded separately from inventory counts.
for name in ('Dawn of the Jedi: Force Storm','Dawn of the Jedi: Force War','Dawn of the Jedi: The Prisoner of Bogan'):
 for n in range(1,6):expected[f'{name} {n}']=None
for title in ('Knights of the Old Republic 0','Knight Errant 0',
              'The Old Republic, Threat of Peace Act 1: Treaty of Coruscant',
              'The Old Republic, Threat of Peace Act 2: New Galactic Order',
              'The Old Republic, Threat of Peace Act 3: Uncertain Surrender',
              'The Old Republic, Blood of the Empire Act 1: Shades of the Sith',
              'The Old Republic, Blood of the Empire Act 2: The Broken World',
              'The Old Republic, Blood of the Empire Act 3: Burn the Future'):expected[title]=None
path=hf_hub_download(REPO,FILE,repo_type='dataset',revision=REV)
found={}
for batch in pq.ParquetFile(path).iter_batches(batch_size=2000):
 for x in batch.to_pylist():
  if x['title'] not in expected or requires_review(x['text']):continue
  if x['title'] in found:raise ValueError('duplicate title: '+x['title'])
  if x['license']!='CC BY-SA 3.0' or x['source']!='Wookieepedia':raise ValueError('unexpected source or license')
  x['sha256']=hashlib.sha256(x['text'].encode()).hexdigest()
  x['upstream_repository']=REPO;x['upstream_revision']=REV
  x['evidence_class']='secondary';x['inventory_work_id']=expected[x['title']]
  found[x['title']]=x
out=Path('data/wookieepedia-comic-summaries.jsonl')
with out.open('w',encoding='utf-8',newline='\n') as f:
 for title in sorted(found):f.write(json.dumps(found[title],ensure_ascii=False,sort_keys=True)+'\n')
missing=sorted(set(expected)-set(found))
print(json.dumps({'expected_titles':len(expected),'found':len(found),'missing':missing,'unmapped_inventory_work_ids':[i['work_id'] for i in inv['issues'] if i['work_id'].rsplit('-',1)[0] not in TEMPLATES]},ensure_ascii=False))
