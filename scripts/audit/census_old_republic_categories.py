"""Reconcile an explicit category-pattern slice of a pinned wiki snapshot.

Usage: PYTHONPATH=... python census_old_republic_categories.py
The output contains only source metadata, not upstream article text. Category
membership is a discovery signal, not proof of relevance, rights or completeness.
"""
import collections,hashlib,json,re
from pathlib import Path
from urllib.parse import unquote,urlsplit
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
REPO='rafa-rrayes/wookieelm-corpus';REV='5d19bba512fa8c65b225c1819d7971db316b871c'
PAT=re.compile(r"(?i)(?:knights of the old republic|the old republic|tales of the jedi|jedi civil war|mandalorian wars|great galactic war|cold war \(galactic|inter-sith wars|new sith wars|old sith wars|great sith war|je.daii)")
manifest=json.loads(Path('manifest.json').read_text());entries={v['path']:v for v in manifest['input_files']};present={};layers=[]
def norm(u):
 p=urlsplit(u or '')
 return (p.hostname or '').casefold()+unquote(p.path).replace('_',' ').casefold()
for path in sorted(Path('data').iterdir()):
 if path.suffix not in ('.jsonl','.parquet'):continue
 b=path.read_bytes();digest=hashlib.sha256(b).hexdigest();e=entries.get(str(path))
 if not e or (e['size'],e['sha256'])!=(len(b),digest):raise ValueError('unregistered or changed layer: '+str(path))
 layers.append({'path':str(path),'sha256':digest})
 if path.suffix=='.jsonl':
  with path.open(encoding='utf8') as f:docs=[json.loads(x) for x in f if x.strip()]
 else:docs=pq.read_table(path).to_pylist()
 for d in docs:
  u=d.get('url') or d.get('source_url') or ''
  if urlsplit(u).hostname=='starwars.fandom.com':present.setdefault(norm(u),set()).add(str(path))
items=[];category_counts=collections.Counter();source_files=[];scanned=0
for i in range(2):
 path=Path(hf_hub_download(REPO,f'pretrain/wookieepedia-{i:05d}-of-00002.parquet',repo_type='dataset',revision=REV,local_files_only=True));
 with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
 source_files.append({'path':f'pretrain/wookieepedia-{i:05d}-of-00002.parquet','sha256':digest})
 for batch in pq.ParquetFile(path).iter_batches(batch_size=2048,columns=['doc_id','title','url','continuity','categories','text']):
  for d in batch.to_pylist():
   scanned+=1;cats=sorted(set(c for c in d.get('categories') or [] if PAT.search(c)))
   if not cats:continue
   category_counts.update(cats);url=d.get('url') or '';text=d.get('text') or '';layers_here=sorted(present.get(norm(url),set()))
   items.append({'doc_id':d['doc_id'],'title':d['title'],'url':url,'continuity':d['continuity'],'matched_categories':cats,'snapshot_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'existing_corpus_layers':layers_here,'status':'url_present' if layers_here else 'discovery_only','rights_review':'not_established_by_category'})
ids=[v['doc_id'] for v in items]
if len(ids)!=len(set(ids)):raise ValueError('duplicate snapshot document IDs')
items.sort(key=lambda x:x['doc_id']);result={'scope':'Category-pattern slice of a pinned WookieeLM snapshot compared by normalized URL against current manifest text layers. Selection is non-exhaustive; categories can be overbroad or absent, and URL presence does not establish era relevance, article completeness or rights. No source article text is reproduced.','upstream_repository':REPO,'upstream_revision':REV,'source_files':source_files,'category_pattern':PAT.pattern,'snapshot_records_scanned':scanned,'data_layers_scanned':layers,'matched_categories':len(category_counts),'matched_records':len(items),'records_with_existing_url':sum(bool(x['existing_corpus_layers']) for x in items),'records_without_existing_url':sum(not x['existing_corpus_layers'] for x in items),'category_counts':dict(sorted(category_counts.items())),'items':items}
Path('evaluation/old-republic-category-census.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print('snapshot records',scanned,'categories',len(category_counts),'matched',len(items),'present',result['records_with_existing_url'],'absent',result['records_without_existing_url'])
