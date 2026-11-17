"""Link Threat of Peace act appearance targets to manifest-verified text records.

Exact normalized URL matches only; redirects, aliases, article completeness,
comic page fidelity and rights are not established. No model calls.
"""
import collections,hashlib,json
from pathlib import Path
from urllib.parse import urlsplit,unquote
import pyarrow.parquet as pq

def sha(b):return hashlib.sha256(b).hexdigest()
def norm(u):
 p=urlsplit(u or '');return (p.hostname or '').casefold()+unquote(p.path).replace('_',' ').casefold()
def records(p):
 if p.suffix=='.jsonl':
  with p.open(encoding='utf8') as f:
   for line in f:
    if line.strip():yield json.loads(line)
 else:
  for batch in pq.ParquetFile(p).iter_batches(batch_size=2048):yield from batch.to_pylist()
m=json.loads(Path('manifest.json').read_text());entries={v['path']:v for v in m['input_files']};layers=[];index=collections.defaultdict(list)
for p in sorted(Path('data').iterdir()):
 if p.suffix not in ('.jsonl','.parquet'):continue
 b=p.read_bytes();entry=entries[str(p)];assert (len(b),sha(b))==(entry['size'],entry['sha256']);layers.append({'path':str(p),'sha256':sha(b)})
 for r in records(p):
  u=r.get('url') or r.get('source_url') or '';text=r.get('text') or ''
  if urlsplit(u).hostname=='starwars.fandom.com' and text:
   index[norm(u)].append({'path':str(p),'title':r.get('title'),'url':u,'section':r.get('section'),'revision_id':r.get('revision_id') or r.get('source_revision_id'),'text_sha256':sha(text.encode()),'license':r.get('license'),'evidence_class':r.get('evidence_class')})
source=Path('data/wookieepedia-threat-webcomic-appearance-indices.jsonl');targets={}
for r in records(source):
 for a in r['appearances']:
  key=norm(a['target_url']);x=targets.setdefault(key,{'target':a['target'],'target_url':a['target_url'],'act_ids':set(),'categories':set()});x['act_ids'].add(r['work_id']);x['categories'].add(a['category'])
items=[]
for key,x in sorted(targets.items()):
 hits=index.get(key,[]);items.append({'target':x['target'],'target_url':x['target_url'],'act_ids':sorted(x['act_ids']),'categories':sorted(x['categories']),'matching_corpus_records':hits,'status':'exact_url_present' if hits else 'no_exact_url_match'})
result={'scope':'Exact normalized target URL matching against manifest-verified text layers; strips fragments and normalizes case and underscores. Aliases, redirects, label ambiguity, relevance, primary comic content, page fidelity and rights are not established by a match.','appearance_index_sha256':sha(source.read_bytes()),'data_layers_scanned':layers,'distinct_targets':len(items),'targets_with_exact_url_match':sum(bool(x['matching_corpus_records']) for x in items),'targets_without_exact_url_match':sum(not x['matching_corpus_records'] for x in items),'items':items}
Path('evaluation/threat-webcomic-target-reconciliation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('Distinct targets',len(items),'matched',result['targets_with_exact_url_match'],'unmatched',result['targets_without_exact_url_match'])
