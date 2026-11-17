"""Acquire three quote-screened sections of a pinned Wikipedia article."""
import hashlib,json,re,requests
from pathlib import Path
url='https://en.wikipedia.org/w/api.php';s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)'
r=s.get(url,params={'action':'query','format':'json','formatversion':2,'prop':'extracts|revisions|info','inprop':'url','explaintext':1,'rvprop':'ids|timestamp','titles':'Star Wars: Knight Errant','redirects':1},timeout=30);r.raise_for_status();p=r.json()['query']['pages'][0];rev=p['revisions'][0];source=p['extract'];source_hash=hashlib.sha256(source.encode()).hexdigest()
if rev['revid']!=1355697941 or source_hash!='1d24c6838fd7c40f8451abfe72a8075d5586aeff4a7ae095592ea0bc514ba64a':raise ValueError('Source changed; review and pin a new revision')
rows=[]
for label in ['Comics','Plot summary','Novel']:
 match=re.search(r'(?m)^\s*(={2,})\s*'+re.escape(label)+r'\s*\1\s*$',source)
 if not match:raise ValueError('Missing section '+label)
 nxt=re.search(r'(?m)^\s*={2,}\s*.*?\s*={2,}\s*$',source[match.end():]);text=source[match.end():match.end()+nxt.start() if nxt else len(source)].strip()
 if not text or any(c in text for c in ('"','“','”')):raise ValueError('Empty or quoted section requires review: '+label)
 rows.append({'title':p['title']+' — '+label,'subject':p['title'],'section':label,'url':p['fullurl'],'source_revision_url':'https://en.wikipedia.org/w/index.php?oldid='+str(rev['revid']),'revision':rev['revid'],'timestamp':rev['timestamp'],'text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'full_extract_sha256':source_hash,'license':'CC BY-SA 4.0','license_url':'https://creativecommons.org/licenses/by-sa/4.0/','attribution':'Wikipedia contributors; see linked article history','evidence_class':'secondary','coverage':'Partial Wikipedia publication and plot material; primary comics, novel, branches and unmarked third-party excerpt rights are not established. The article introduction and quoted reviews are excluded.','embedded':False})
Path('data/wikipedia-knight-errant-sections.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows));print('Included',len(rows),'sections at revision',rev['revid'])
