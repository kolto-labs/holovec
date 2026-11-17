import requests, json, time, hashlib, pathlib
S=requests.Session(); S.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs; research dataset)'
titles=['Star Wars: Knights of the Old Republic (video game)','Star Wars: Knights of the Old Republic II – The Sith Lords','Star Wars: The Old Republic','Revan','Kreia','HK-47','Bastila Shan','Atton Rand','Juhani (Star Wars)','List of Star Wars: Knights of the Old Republic characters','Star Wars: Knights of the Old Republic (comics)','Tales of the Jedi (comics)','The Sith Lords Restored Content Modification']
out=[]
for title in titles:
 r=S.get('https://en.wikipedia.org/w/api.php',params={'action':'query','format':'json','formatversion':2,'prop':'extracts|revisions|info','explaintext':1,'rvprop':'ids|timestamp','inprop':'url','redirects':1,'titles':title},timeout=30); r.raise_for_status(); p=r.json()['query']['pages'][0]
 if 'missing' in p: print('missing',title); continue
 text=p.get('extract',''); rev=p.get('revisions',[{}])[0]; out.append({'title':p['title'],'url':p.get('fullurl'),'revision':rev.get('revid'),'timestamp':rev.get('timestamp'),'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'license':'CC BY-SA 4.0','attribution':'Wikipedia contributors; see article revision history'}); time.sleep(.3)
pathlib.Path('data/wikipedia.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in out)); print('acquired',len(out),'pages')
