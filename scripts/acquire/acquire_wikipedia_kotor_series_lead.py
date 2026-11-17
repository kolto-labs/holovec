"""Acquire a pinned Wikipedia series introduction; no inference or primary media."""
import hashlib,json
from pathlib import Path
import requests

url='https://en.wikipedia.org/w/api.php'
s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)'
r=s.get(url,params={'action':'query','format':'json','formatversion':2,'prop':'extracts|revisions|info','inprop':'url','explaintext':1,'exintro':1,'rvprop':'ids|timestamp','titles':'Star Wars: Knights of the Old Republic'},timeout=30);r.raise_for_status();p=r.json()['query']['pages'][0]
t=p['extract'];rev=p['revisions'][0];digest=hashlib.sha256(t.encode()).hexdigest()
if rev['revid']!=1384348506 or digest!='04dbf4b53748d96bb64f28aca601135ef957682fb40f4fef745e0dbda9d0fc82':raise ValueError('Current page changed; review and pin a new revision before acquisition')
if any(c in t for c in ('"','“','”')):raise ValueError('Quotation review required')
row={'title':p['title']+' — introduction','url':p['fullurl'],'source_revision_url':'https://en.wikipedia.org/w/index.php?oldid='+str(rev['revid']),'revision':rev['revid'],'timestamp':rev['timestamp'],'text':t,'sha256':digest,'license':'CC BY-SA 4.0','license_url':'https://creativecommons.org/licenses/by-sa/4.0/','attribution':'Wikipedia contributors; see linked article history','coverage':'Secondary franchise introduction only; not a complete article or primary game, comic or book source. Third-party text rights are not independently established.','embedded':False}
Path('data/wikipedia-kotor-series-introduction.jsonl').write_text(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n');print('Included pinned introduction',rev['revid'],digest)
