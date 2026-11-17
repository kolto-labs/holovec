"""Map linked subjects in five War issues to current corpus source records.

URLs are normalized for case, underscores and repeated spaces; links can include other eras and incidental subjects.
This is a discovery crosswalk, not a claim of complete issue or primary coverage.
"""
import collections,hashlib,json,re
from pathlib import Path
from urllib.parse import unquote,urlsplit
import pyarrow.parquet as pq

def digest(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def norm(url):
 u=urlsplit(url or '');return (u.netloc.casefold(),re.sub(r'\s+', ' ', unquote(u.path).replace('_',' ')).rstrip('/').casefold())
indices='data/wookieepedia-comic-appearance-indices.jsonl';corpus='unified/corpus.parquet';coverage=json.loads(Path('unified/coverage.json').read_text())
if digest(corpus)!=coverage['output_sha256']:raise ValueError('Unified corpus mismatch')
wanted={f'kotor-war-{i:03}' for i in range(1,6)};issues={}
for n,line in enumerate(open(indices,encoding='utf8')):
 r=json.loads(line)
 if r.get('work_id') in wanted:issues[r['work_id']]={'index_row':n,'index_text_sha256':r['text_sha256'],'appearances':r['appearances']}
if set(issues)!=wanted:raise ValueError('Missing issue index')
keys={norm(a['target_url']) for x in issues.values() for a in x['appearances'] if a.get('target_url')};lookup=collections.defaultdict(list)
redirect_from=norm("https://starwars.fandom.com/wiki/Zayne_Carrick%27s_lightsaber")
redirect_targets=["Zayne Carrick's lightsaber (disambiguation)","Zayne Carrick's first lightsaber","Zayne Carrick's second lightsaber"];redirect_records=collections.defaultdict(list)
pf=pq.ParquetFile(corpus)
for batch in pf.iter_batches(batch_size=512,columns=['source_layer','source_row','title','source_url','text_sha256']):
 for r in batch.to_pylist():
  key=norm(r['source_url'])
  if key in keys:lookup[key].append(r)
  if r['title'] in redirect_targets:redirect_records[r['title']].append(r)
results=[]
for issue_id,issue in sorted(issues.items()):
 appearances=[]
 for a in issue['appearances']:
  if not a.get('target_url'):continue
  item={'category':a['category'],'label':a['label'],'target':a['target'],'target_url':a['target_url'],'records':lookup.get(norm(a['target_url']),[])}
  if norm(a['target_url'])==redirect_from:
   item['redirect_disambiguation']={'source_revision_id':'13801445','source_wikitext_sha256':'4cfa5ec6794fa9df8e96e33c33224da207d04807be54bb2e523bd39a6f89843f','scope':'The wiki link redirects to a disambiguation page. Candidate records are contextual alternatives; the particular saber in this issue is not established.','target_records':dict(redirect_records)}
  appearances.append(item)
 results.append({'work_id':issue_id,'appearance_index_row':issue['index_row'],'appearance_index_text_sha256':issue['index_text_sha256'],'linked_occurrences':len(appearances),'with_at_least_one_text_record':sum(bool(a['records']) for a in appearances),'appearances':appearances})
unique_matched=set(keys)&set(lookup);out={'scope':'Metadata-only exact URL linkage from five KOTOR War issue appearance indices to unified corpus records. One redirect to a lightsaber disambiguation page is followed without choosing between its candidates; other redirects and aliases are not resolved. Generic subjects, duplicates and other eras may be linked. Record presence does not prove relevance, licensing clearance or complete story coverage.','source_hashes':{indices:digest(indices),corpus:coverage['output_sha256']},'counts':{'issues':len(results),'linked_occurrences':sum(x['linked_occurrences'] for x in results),'occurrences_with_text':sum(x['with_at_least_one_text_record'] for x in results),'distinct_target_urls':len(keys),'distinct_targets_with_text':len(unique_matched),'distinct_targets_without_text':len(keys-unique_matched),'unmatched_targets_with_disambiguation_context':int(redirect_from in keys-unique_matched and len(redirect_records)==3)},'items':results}
Path('evaluation/kotor-war-appearance-context.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(out['counts'])
