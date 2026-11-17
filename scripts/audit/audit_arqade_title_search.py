"""Find previously held or unrepresented game questions in bounded API searches.

This is a discovery audit only: it publishes IDs and dispositions, not post text.
Search ranking, API limits, title variants and deleted posts preclude a census.
"""
import datetime,hashlib,json,re,time
from pathlib import Path
import requests
BASE='https://api.stackexchange.com/2.3/search/advanced'
queries=['kotor','knights of the old republic','sith lords','swtor']
existing_files=['data/arqade.jsonl','data/arqade-swtor.jsonl','data/arqade-swtor-revision-recovery.jsonl']
existing=set()
for f in existing_files:
 with open(f,encoding='utf-8') as h:
  for line in h:existing.add(json.loads(line)['id'])
held={x['id']:x['reason'] for x in json.loads(Path('evaluation/arqade-swtor-screen.json').read_text())['held']}
held.update({x['id']:x['reason'] for x in json.loads(Path('evaluation/arqade-swtor-revision-recovery.json').read_text())['dispositions'] if x['reason']!='recovered'})
pattern=re.compile(r'\b(kotor|swtor|knights of the old republic)\b',re.I)
tags={'star-wars-the-old-republic','star-wars-knights-of-the-old-republic','star-wars-knights-of-the-old-republic-2'}
session=requests.Session(); session.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)'
found={}; results=[]
for query in queries:
 page=1;count=0
 while True:
  r=session.get(BASE,params={'site':'gaming','q':query,'pagesize':100,'page':page},timeout=45);r.raise_for_status();d=r.json()
  if d.get('error_id'):raise RuntimeError(d.get('error_name'))
  count+=len(d['items'])
  for post in d['items']:
   if not (pattern.search(post.get('title','')) or tags.intersection(post.get('tags',[]))):continue
   ident='question:'+str(post['question_id'])
   if ident not in existing:found[ident]={'id':ident,'reason':held.get(ident,'not found in selected text layers; requires rights and relevance review')}
  time.sleep(max(.2,d.get('backoff',0)))
  if not d.get('has_more'):break
  page+=1
 results.append({'query':query,'retrieved':count,'pages':page})
out={'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'api':'https://api.stackexchange.com/docs/advanced-search','description':'Bounded search of Arqade API results; include only a matching game tag or an explicit KOTOR, SWTOR or Knights of the Old Republic title. No post body is retained.','queries':results,'existing_layer_sha256':{f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in existing_files},'unrepresented_candidates':sorted(found.values(),key=lambda x:x['id']),'limitations':'Search API may omit relevant variants or deleted posts and is not a complete census. A previously held item is not cleared merely by rediscovery; relevance and rights require review.'}
Path('evaluation/arqade-game-search-gap.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print('Unrepresented',len(found),'new leads',sum(x['id'] not in held for x in found.values()))
