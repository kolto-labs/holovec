"""Acquire articles from the two Wikipedia KotOR categories using the public API."""
import requests,time,json,hashlib,pathlib
s=requests.Session(); s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)';url='https://en.wikipedia.org/w/api.php'
def get(**p):
 r=s.get(url,params={'action':'query','format':'json','formatversion':2,**p},timeout=30);r.raise_for_status();time.sleep(.25);return r.json()
titles=set()
for cat in ['Category:Star Wars: Knights of the Old Republic','Category:Star Wars: Knights of the Old Republic characters']:
 cont={}
 while True:
  d=get(list='categorymembers',cmtitle=cat,cmtype='page',cmlimit=500,**cont)
  titles.update(x['title'] for x in d['query']['categorymembers'])
  if 'continue' not in d:break
  cont=d['continue']
rows=[]
for title in sorted(titles):
 d=get(prop='extracts|revisions|info',explaintext=1,rvprop='ids|timestamp',inprop='url',titles=title,redirects=1);p=d['query']['pages'][0]
 text=p.get('extract','');rev=p.get('revisions',[{}])[0]
 if not text or not rev.get('revid'):continue
 rows.append({'title':p['title'],'url':p.get('fullurl'),'revision':rev['revid'],'timestamp':rev.get('timestamp'),'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'license':'CC BY-SA 4.0','attribution':'Wikipedia contributors; see article revision history','selection':'KotOR Wikipedia categories'})
pathlib.Path('data/wikipedia-categories.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows));print('category titles',len(titles),'records',len(rows))
