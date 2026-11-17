"""Reconcile historical era holds against current text URLs and comic indices.

An alternate record for a URL is not clearance of the originally held text.
No raw text or embeddings are produced by this metadata-only audit.
"""
import collections,hashlib,json
from pathlib import Path
from urllib.parse import unquote,urlparse
import pyarrow.parquet as pq

def key(url):
 if not isinstance(url,str):return None
 p=urlparse(url)
 if p.hostname not in ('starwars.fandom.com','www.starwars.fandom.com') or not p.path.startswith('/wiki/'):return None
 return unquote(p.path[len('/wiki/'):]).replace('_',' ')
manifest=json.loads(Path('manifest.json').read_text());holdpath=Path('evaluation/era-date-screening.json');held=json.loads(holdpath.read_text())['held'];names={key(x['url']):x for x in held};assert len(names)==len(held) and None not in names
matches=collections.defaultdict(list);index=collections.defaultdict(list);inputs={}
for e in manifest['input_files']:
 name=e['path'];p=Path(name)
 if not name.startswith('data/') or p.suffix not in ('.jsonl','.parquet'):continue
 with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
 if digest!=e['sha256']:raise ValueError('manifest mismatch '+name)
 inputs[name]=digest
 if p.suffix=='.jsonl':
  def read():
   with p.open(encoding='utf-8') as h:
    for line in h:
     if line.strip():yield json.loads(line)
 else:
  def read():
   pf=pq.ParquetFile(p);cols=[c for c in ('url','source_url','revision','revision_id','text_sha256','sha256') if c in pf.schema_arrow.names]
   for b in pf.iter_batches(columns=cols,batch_size=512):yield from b.to_pylist()
 for r in read():
  for u in {r.get('url'),r.get('source_url')}:
   title=key(u)
   if title in names:matches[title].append({'layer':name,'revision':r.get('revision_id') or r.get('revision'),'text_sha256':r.get('text_sha256') or r.get('sha256')})
  if 'appearance' in p.name:
   for a in r.get('appearances',[]):
    title=key(a.get('target_url'))
    if title in names:index[title].append({'layer':name,'work_id':r.get('work_id'),'index_revision':r.get('revision_id')})
results=[]
for title,original in sorted(names.items()):
 alt=sorted({(x['layer'],str(x['revision'] or ''),str(x['text_sha256'] or '')) for x in matches[title]});appear=sorted({(x['layer'],str(x['work_id'] or ''),str(x['index_revision'] or '')) for x in index[title]})
 results.append({'title':title,'url':original['url'],'historical_held_text_sha256':original['text_sha256'],'historical_reasons':original['reasons'],'matching_records':[{'layer':a,'revision':b or None,'text_sha256':c or None} for a,b,c in alt],'appearance_indices':[{'layer':a,'work_id':b or None,'index_revision':c or None} for a,b,c in appear]})
out={'description':'Normalized exact URL comparison of 97 historically held titles with current manifest text layers and editorial comic appearance indices. Different versions or partial leads do not clear the original held text. Exact-title matching does not resolve redirects or aliases.','hold_file_sha256':hashlib.sha256(holdpath.read_bytes()).hexdigest(),'input_layer_sha256':inputs,'historical_holds':len(results),'subjects_with_matching_record':sum(bool(x['matching_records']) for x in results),'subjects_without_matching_record':sum(not x['matching_records'] for x in results),'subjects_linked_by_appearance_indices':sum(bool(x['appearance_indices']) for x in results),'items':results}
Path('evaluation/era-hold-current-reconciliation.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print('Historical holds',len(results),'subjects represented',out['subjects_with_matching_record'],'without exact match',out['subjects_without_matching_record'],'comic linked',out['subjects_linked_by_appearance_indices'])
